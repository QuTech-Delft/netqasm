# from netqasm.logging.glob import get_netqasm_logger
# from netqasm.qlink_compat import EPRType
# from netqasm.runtime.application import default_app_instance
# from netqasm.sdk import EPRSocket
# from netqasm.sdk.external import NetQASMConnection, simulate_application

# logger = get_netqasm_logger()

# num = 10


# def run_alice():
#     epr_socket = EPRSocket("bob")
#     outcomes = []
#     with NetQASMConnection("alice", epr_sockets=[epr_socket]):
#         ent_infos = epr_socket.create(number=num, tp=EPRType.M)
#         for ent_info in ent_infos:
#             outcomes.append(ent_info.measurement_outcome)
#     return outcomes


# def run_bob():
#     epr_socket = EPRSocket("alice")
#     outcomes = []
#     with NetQASMConnection("bob", epr_sockets=[epr_socket]):
#         ent_infos = epr_socket.recv(number=num, tp=EPRType.M)
#         for ent_info in ent_infos:
#             outcomes.append(ent_info.measurement_outcome)
#     return outcomes


# def test_create_epr_m():
#     app_instance = default_app_instance(
#         [
#             ("alice", run_alice),
#             ("bob", run_bob),
#         ]
#     )
#     outcomes = simulate_application(
#         app_instance, use_app_config=False, enable_logging=False
#     )[0]

#     print(outcomes)
#     for i in range(num):
#         assert int(outcomes["app_alice"][i]) == int(outcomes["app_bob"][i])


# if __name__ == "__main__":
#     for _ in range(100):
#         test_create_epr_m()
