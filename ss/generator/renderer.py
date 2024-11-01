from typing import Any, Optional
from ss.configure.blueprint import Blueprint
from os.path import exists
from ss.configure.schema import *
from ss.generator.functions.action import Action
from ss.generator.functions.action_flow import ActionFlow
from ss.generator.functions.doc import Doc
from ss.generator.functions.weblink import Weblink
from ss.generator.functions.git_repo import GitRepo
from ss.generator.functions.nix_package import NixPackage
from ss.generator.functions.sh import Sh


class Renderer:
    def resolve_all_includes(self, blueprint: Blueprint):
        return [
            self.resolve_import(name=item[0], item=item[1])
            for item in blueprint.includes.items()
        ]

    def resolve_import(self, name: str, item: dict):
        local_path = item.get("local_path")
        gen_root = item.get("gen_root")
        ss_nix = f"{gen_root}/ss.nix"
        ss_yaml = f"{local_path}/ss.yaml"
        default_nix = f"{local_path}/default.nix"
        flake_nix = f"{local_path}/flake.nix"
        shell_nix = f"{local_path}/shell.nix"

        if exists(ss_yaml):
            return name, f"{name} = pkgs.callPackage {ss_nix} {{}};"

        elif exists(default_nix):
            if item.get(CALLABLE, True) == False:
                return name, f"{name} = import {default_nix};"
            else:
                return name, f"{name} = pkgs.callPackage {default_nix} {{}};"

        elif exists(flake_nix):
            return name, f"{name} = pkgs.getFlake {flake_nix} {{}};"

        elif exists(shell_nix):
            return name, f"{name} = pkgs.callPackage {shell_nix} {{}};"
        else:
            return name, None

    def _is_path(self, value: str) -> bool:
        return value.startswith("./") or value.startswith("../")

    def _is_multiple_lines(self, value: str) -> bool:
        return "\n" in value

    def render_let_in(self, vars: dict) -> str:
        if len(vars) == 0:
            return ""

        return f"""
            let
                { LINE_BREAK.join([f'{key} = {value};' for key, value in vars.items()]) }
            in
        """

    def render_call_father(self, name: str, unit: dict, blueprint: Blueprint) -> dict:
        params = self.extract_params(unit)

        father_name = self.father_name(unit=unit, blueprint=blueprint)

        intreface = f"_{name}"

        if father_name is None:
            result = {}
        else:
            if len(params) == 0:
                result = {"fatherUnit": f"{father_name}.{intreface} {{}}"}
            else:
                vars = SPACE.join(
                    [
                        f"{key}={self.render_value(key, value, blueprint=blueprint)};"
                        for key, value in params.items()
                    ]
                )
                result = {"fatherUnit": f"{father_name}.{intreface} {{ { vars } }}"}

        return result

    def father_name(self, unit: dict, blueprint: Blueprint) -> Optional[str]:
        source = unit.get(K_SOURCE)

        if source is None:
            return None

        source_comp = source.split(".")

        if not isinstance(source, str):
            return None

        if len(source_comp) < 2:
            return None

        resolvable_includes = [
            item
            for item in blueprint.includes.keys()
            if blueprint.includes[item].get("blueprint") is not None
        ]

        if source_comp[0] not in resolvable_includes:
            return None

        return source_comp[0]

    def merge_all_fields(self, unit: dict, blueprint: Blueprint) -> dict:
        father_name = self.father_name(unit=unit, blueprint=blueprint)

        if father_name is not None:
            unit = {
                key: unit.get(key, f"fatherUnit.{key} or null")
                for key in PRE_DEFINED_KEYS
            }
            unit[K_SOURCE] = f"fatherUnit.{K_SOURCE}"

        return unit

    def extract_params(self, unit: dict) -> dict:
        return {k: v for k, v in unit.items() if k not in PRE_DEFINED_KEYS}

    def render_unit(self, unit: dict, blueprint: Blueprint) -> str:
        # resolve all fields from includes
        unit = self.merge_all_fields(unit=unit, blueprint=blueprint)

        params = self.extract_params(unit)

        unit = {k: v for k, v in unit.items() if k in PRE_DEFINED_KEYS}

        def process_render(key: str, value: Any):
            if key == K_DOC and value is not None:
                return Doc(value).render()
            else:
                return self.render_value(key, value, blueprint=blueprint, params=params)

        return LINE_BREAK.join(
            [
                f"{key}={process_render(key=key, value=value)};"
                for key, value in unit.items()
            ]
        )

    def render_map(
        self, name: str, data: dict, blueprint: Blueprint, params: dict = {}
    ) -> str:
        function = self.find_function(
            name=name, value=data, params=params, blueprint=blueprint
        )

        if function is not None:
            return function.render()
        else:
            return f"""
                {{
                    { LINE_BREAK.join([f'{key} = {self.render_value(key, value, blueprint=blueprint, params=params)};' for key, value in data.items() ]) }
                }}
            """

    def render_value(
        self, name: str, value: Any, blueprint: Blueprint, params: dict = {}
    ) -> str:
        if value == None:
            return "null"
        elif isinstance(value, list):
            return f"""[{LINE_BREAK.join(map(lambda x: f'{self.render_value(f'{name}[{x[0]}]', x[1], blueprint, params)}', enumerate(value)))}]"""
        elif isinstance(value, dict):
            return self.render_map(
                name=name, data=value, params=params, blueprint=blueprint
            )
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, str) and self._is_path(value):
            return value
        elif isinstance(value, str) and self._is_multiple_lines(value):
            q = "''"
            return f"""
                {q}{value}{q}
            """
        elif (
            name in PRE_DEFINED_KEYS
        ):  # in predefined keys, the text by default is supposed to be nix code, don't add quote
            return f"{str(value)}"
        elif isinstance(value, float):
            return f"{str(value)}"
        else:
            return f'"{str(value)}"'

    def find_function(self, name: str, value: dict, params: dict, blueprint: Blueprint):
        sh = value.get(F_SH)
        url = value.get(F_URL)
        git = value.get(F_GIT)
        action = value.get(F_ACTION)
        action_flow = value.get(F_ACTION_FLOW)
        doc = value.get(F_DOC)

        if sh is not None:
            return Sh(name=name, content=sh)
        elif action is not None and isinstance(action, str):
            return Action(name=name, value=action, blueprint=blueprint, renderer=self)
        elif action is not None and isinstance(action_flow, str):
            return ActionFlow(
                name=name, value=action, blueprint=blueprint, renderer=self
            )
        elif doc is not None:
            return Doc(unit_name=name, content=doc)
        elif name == K_SOURCE:
            if url is not None and isinstance(url, str):
                return Weblink(value=url, params=params, blueprint=blueprint)
            elif git is not None and isinstance(git, dict):
                return GitRepo(value=git, params=params)
            else:
                return NixPackage(value=name, params=params)

        else:
            return None
