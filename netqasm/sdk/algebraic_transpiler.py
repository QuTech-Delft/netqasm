import numpy as np
from netqasm.lang.instr import vanilla, nv, core
from netqasm.lang.operand import Immediate

SIGMA_X = np.array([[0, 1], [1, 0]], dtype=complex)
SIGMA_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
SIGMA_Z = np.array([[1, 0], [0, -1]], dtype=complex)

def get_unitary(instr):
    """Maps vanilla NetQASM instructions to their SU(2) unitaries."""
    PI = np.pi
    
    if isinstance(instr, vanilla.GateHInstruction):
        return (1/np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
    elif isinstance(instr, vanilla.GateXInstruction):
        return SIGMA_X
    elif isinstance(instr, vanilla.GateYInstruction):
        return SIGMA_Y
    elif isinstance(instr, vanilla.GateZInstruction):
        return SIGMA_Z
    elif isinstance(instr, vanilla.GateSInstruction):
        return np.array([[1, 0], [0, 1j]], dtype=complex)
    elif isinstance(instr, vanilla.GateTInstruction):
        return np.array([[1, 0], [0, np.exp(1j * PI / 4)]], dtype=complex)
    elif isinstance(instr, vanilla.GateKInstruction):
        return (1/np.sqrt(2)) * np.array([[1, -1j], [1, 1j]], dtype=complex)
    elif isinstance(instr, vanilla.RotXInstruction):
        n, d = instr.angle_num.value, instr.angle_denom.value
        theta = n * PI / (2 ** d)
        return np.cos(theta/2)*np.eye(2) - 1j*np.sin(theta/2)*SIGMA_X
    elif isinstance(instr, vanilla.RotYInstruction):
        n, d = instr.angle_num.value, instr.angle_denom.value
        theta = n * PI / (2 ** d)
        return np.cos(theta/2)*np.eye(2) - 1j*np.sin(theta/2)*SIGMA_Y
    elif isinstance(instr, vanilla.RotZInstruction):
        n, d = instr.angle_num.value, instr.angle_denom.value
        theta = n * PI / (2 ** d)
        return np.cos(theta/2)*np.eye(2) - 1j*np.sin(theta/2)*SIGMA_Z
    
    return np.eye(2)

def decompose_to_nv(U, qubit_register, lineno=None):
    """
    Decomposes an arbitrary SU(2) matrix into minimal NV native gates.
    """
    alpha = np.angle(U[0, 0]) + np.angle(-U[0, 1])
    beta = 2 * np.arccos(np.clip(np.abs(U[0, 0]), -1.0, 1.0))
    gamma = np.angle(U[0, 0]) - np.angle(-U[0, 1])
    
    def approximate_angle(theta, fixed_d=4):
        # Maps continuous optimal angle back to NetQASM fractional format
        theta = theta % (2 * np.pi)
        n = int(round(theta * (2**fixed_d) / np.pi))
        return n, fixed_d

    nv_instructions = []
    for angle, axis in [(gamma, 'Z'), (beta, 'Y'), (alpha, 'Z')]:
        if not np.isclose(angle, 0.0, atol=1e-5):
            n, d = approximate_angle(angle)
            if axis == 'X':
                instr = nv.RotXInstruction(lineno=lineno, reg=qubit_register, imm0=Immediate(n), imm1=Immediate(d))
            elif axis == 'Y':
                instr = nv.RotYInstruction(lineno=lineno, reg=qubit_register, imm0=Immediate(n), imm1=Immediate(d))
            elif axis == 'Z':
                instr = nv.RotZInstruction(lineno=lineno, reg=qubit_register, imm0=Immediate(n), imm1=Immediate(d))
            nv_instructions.append(instr)
            
    return nv_instructions

def optimize_subroutine(instructions):
    optimized = []
    current_u = {} 
    
    single_qubit_classes = (
        vanilla.GateHInstruction, vanilla.GateXInstruction, vanilla.GateYInstruction, vanilla.GateZInstruction,
        vanilla.GateSInstruction, vanilla.GateTInstruction, vanilla.GateKInstruction,
        vanilla.RotXInstruction, vanilla.RotYInstruction, vanilla.RotZInstruction
    )
    
    for instr in instructions:
        if isinstance(instr, single_qubit_classes):
            q_reg = instr.reg
            U_op = get_unitary(instr)
            if q_reg not in current_u:
                current_u[q_reg] = np.eye(2, dtype=complex)
            # Multiply latest operation
            current_u[q_reg] = U_op @ current_u[q_reg]
            
        # The SDK Builder injects redundant "set Qx y" commands before every single gate.
        # Absorb these if we are currently accumulating a block to prevent breaking the SU(2) trajectory.
        elif isinstance(instr, core.SetInstruction) and instr.reg in current_u:
            continue
            
        else:
            # Flush accumulated unitaries on multi-qubit or structural gates
            for q_reg, U in list(current_u.items()):
                if not np.allclose(U, np.eye(2)):
                    optimized.extend(decompose_to_nv(U, q_reg, lineno=getattr(instr, 'lineno', None)))
                del current_u[q_reg]
            optimized.append(instr)
            
    for q_reg, U in current_u.items():
        if not np.allclose(U, np.eye(2)):
            optimized.extend(decompose_to_nv(U, q_reg))
            
    return optimized