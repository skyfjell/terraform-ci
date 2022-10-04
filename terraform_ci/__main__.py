from .terraform import TfCLI
from .pipeline import ActionPipeline
from .config import Settings

if __name__ == "__main__":
    settings = Settings().config
    print(settings)

    TfCLI.set_version(version=settings.terraform.version)
    TfCLI.set_token(host=settings.terraform.host, token=settings.terraform.token)

    if settings.mode == "plan":
        (
            ActionPipeline(settings)
            .format()
            .imports()
            .init()
            .plan()
            .scan()
            .report()
        )
    else:
        (
            ActionPipeline(settings)
            .init()
            .plan()
            .apply()
            .report()
        )
