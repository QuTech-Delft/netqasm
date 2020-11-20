class NetQASMSyntaxError(SyntaxError):
    pass


class NetQASMInstrError(ValueError):
    pass


class NoCircuitRuleError(RuntimeError):
    pass


class NotAllocatedError(RuntimeError):
    pass
