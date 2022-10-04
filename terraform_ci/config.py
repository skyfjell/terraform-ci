from typing import Dict, Literal, Any
from pydantic import BaseModel, BaseSettings, Field, validator
from pydantic.validators import str_validator
from pydantic.env_settings import SettingsSourceCallable
from re import sub
import os
import sys
import yaml


def coerce_empty(val: str | None) -> str | None:
    if isinstance(val, str):
        if val.strip() == "":
            return None
    return val


class GithubStr(str):
    @classmethod
    def __get_validators__(cls):
        yield str_validator
        yield coerce_empty


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


def to_camel(s):
    s = sub(r"(_|-)+", " ", s).title().replace(" ", "")
    return ''.join([s[0].lower(), s[1:]])


class BaseSchema(BaseModel):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True


class TerraformConfig(BaseSchema):
    version: GithubStr | None
    host: GithubStr | None = Field("app.terraform.io")
    token: GithubStr | None
    init_mode: Literal["migrate"] | Literal["reconfigure"] | Literal["upgrade"] | None

    @validator("init_mode", pre=True)
    def v_init_mode(cls, value: str | None):
        if value.strip() == "":
            value = None
        if value not in ["migrate", "reconfigure", "upgrade", None]:
            print("::error title=Terraform Init::Unsupported arguement.")
            sys.exit(1)
        return value


class GithubConfig(BaseSchema):
    token: GithubStr | None


class ImportConfig(BaseSchema):
    address: str
    id: str

    @validator("address")
    def v_address(cls, value: str):
        return value.replace(r'"', r'\"')


class ResourceConfig(BaseSchema):
    imports: list[ImportConfig] = Field([])
    replace: list[str] = Field([])

    @validator("imports",  pre=True)
    def v_imports(cls, imports: Any | None):
        if imports:
            if isinstance(imports, str):
                return [ImportConfig(
                    address=itm.split(" ")[0],
                    id=itm.split(" ")[1]
                ) for itm in imports.split(",")]
            return imports
        return []

    @validator("replace",  pre=True)
    def v_replace(cls, replaces: Any | None):
        if replaces:
            if isinstance(replaces, str):
                return [itm.strip().replace(r'"', r'\"') for itm in replaces.split(",")]
            return [itm.strip().replace(r'"', r'\"') for itm in replaces]
        return []


class ActionSettings(BaseSchema):
    mode: Literal["plan"] | Literal["apply"] = Field("plan")
    working_directory: GithubStr = Field(".")
    create_release: bool | GithubStr | None = Field(False)
    terraform: TerraformConfig
    github: GithubConfig
    resource: ResourceConfig

    @validator("mode", pre=True)
    def v_mode(cls, value):
        if value is None or value.strip() == "":
            return "plan"
        if value not in ["plan", "apply"]:
            raise ValueError("Terraform run mode only supports 'plan' or 'apply'.")
        return value


def load_experimental(settings: BaseSettings) -> Dict[str, Any]:

    try:
        if raw := get_env("YAML_CONFIG"):
            return {"config": yaml.safe_load(raw)}
    except Exception as e:
        print(f"::warning title=Experimental Config::Could not load config file, using defaults. Reason:{e}.")
    return {"config": {}}


class Settings(BaseSettings):
    config: ActionSettings

    class Config:
        env_nested_delimiter = '__'

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            """Prioritize ENV settings"""
            return load_experimental, env_settings, init_settings, file_secret_settings
