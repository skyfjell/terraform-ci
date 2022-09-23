import os


def get_env(name: str) -> str | None:
    """Checks the environment variables by name. Since
    the action uses `""` for unset, will return this is 
    as None.

    Args:
        name (str): Name of environment variable

    Returns:
        str | None: Value of environment variable if set, else None
    """

    variable = os.environ.get(name, "").strip()
    if variable == "":
        return None
    return variable



    