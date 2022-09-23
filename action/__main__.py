from .terraform import TfCLI
from .pipeline import ActionPipeline

if __name__ == "__main__":
    TfCLI.set_version()
    TfCLI.set_token()
    (
        ActionPipeline()
        .format()
        .init()
        .plan()
        .scan()
        .debug_report()
        # .report()
    )
