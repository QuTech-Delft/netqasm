from src.protocol import anonymous_transmission


def main(
    app_config=None,
    sender=False,
    receiver=False,
    phi=0.0,
    theta=0.0,
):

    return anonymous_transmission(
        app_name="alice",
        app_config=app_config,
        sender=sender,
        receiver=receiver,
        phi=phi,
        theta=theta,
    )


if __name__ == "__main__":
    main()
