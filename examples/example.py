from netqasm.runtime.application import Application, ApplicationInstance, Program
from netqasm.runtime.interface.config import default_network_config
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import simulate_application


def client():
    with DebugConnection("client") as conn:
        print("this is the client")
        builder = conn.builder

        q = builder.new_qubit()
        r = builder.new_register()
        a = builder.new_array()
        builder.measure(q)

        print(builder.print_instrs())


def run():
    prog_client = Program(party="client", entry=client, args=["app_config"], results=[])
    network_cfg = default_network_config(["delft"])

    app = Application(programs=[prog_client], metadata=None)
    app_instance = ApplicationInstance(
        app=app,
        program_inputs={
            "client": {},
        },
        network=None,
        party_alloc={
            "client": "delft",
        },
        logging_cfg=None,
    )

    simulate_application(
        app_instance=app_instance, network_cfg=network_cfg, use_app_config=False
    )


if __name__ == "__main__":
    run()
