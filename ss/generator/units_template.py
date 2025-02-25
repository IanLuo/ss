from ss.configure import blueprint
from ss.configure.blueprint import Blueprint
from ss.configure.schema_gen import schema, LINE_BREAK, SPACE
from ss.folder import Folder
from .renderer import Renderer


class UnitsTemplate:
    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint
        self.renderer = Renderer()

    def render_unit(self, name, unit):
        params = self.renderer.extract_params(unit=unit)

        if self.blueprint.is_root_blueprint:
            return f"""
                {name} = (
                  {self.renderer.render_let_in(self.renderer.render_call_father(name=name, unit=unit, blueprint=self.blueprint))}
                sslib.defineUnit
                {{
                    name = "{name}";
                    {self.renderer.render_unit(unit=unit, blueprint=self.blueprint)}
                }});
            """
        else:
            render_call_father = (
                lambda name, unit, blueprint: self.renderer.render_call_father(
                    name=name, unit=unit, blueprint=self.blueprint
                )
            )

            return f"""
            {name} = _{name} {{
            }};

            _{name} = (
            {{
                {",".join([f"{key} ? {self.renderer.render_value(key, value, blueprint=self.blueprint)}" for key, value  in params.items()])}
            }}:
            {self.renderer.render_let_in(render_call_father(name, unit, blueprint) or {})}
            {{

              name = "{name}";
              {self.renderer.render_unit(unit=unit, blueprint=self.blueprint)}
           }});"""

    def render_actions(self, actions: dict) -> str:
        return f"""
        actions = {{
            {LINE_BREAK.join([f"{name} = {self.renderer.render_value(name=name, value=action, blueprint=self.blueprint)};" for name, action in actions.items()])}
        }};
        """

    def render_onstart(self, onstart: dict) -> str:
        return f"""
            onstart = { self.renderer.render_value(name='onstart', value=onstart, blueprint=self.blueprint) };
        """

    def render_services(self, services: dict) -> str:
        return f"""
            services = { self.renderer.render_value(name='services', value=services, blueprint=self.blueprint) };
        """

    def render(self) -> str:
        line_break = LINE_BREAK
        space = SPACE

        names = list(map(lambda x: x.replace(".", "_"), self.blueprint.units.keys()))

        render_units_in_sources = line_break.join(
            [
                self.render_unit(name, value)
                for name, value in self.blueprint.units.items()
            ]
        )

        default_imports = ["pkgs", "system", "name", "version", "lib", "sslib"]
        included_imports = [
            item[0]
            for item in self.renderer.resolve_all_includes(blueprint=self.blueprint)
            if item[1] is not None
        ]
        all_import = included_imports + default_imports
        all_interfaces = (
            space.join(map(lambda x: f"_{x}", names))
            if not self.blueprint.is_root_blueprint
            else ""
        )

        return f"""
	{{  {','.join(all_import) } }}:
		let
            metadata = {{ inherit name version; }};

            system = sslib.env.system;
            workingFolder = {Folder(self.blueprint.root).gen_folder_path};
            logFolder = "${{workingFolder}}/log";
            dataFolder = "${{workingFolder}}/dataFolder";

            {render_units_in_sources}

            { self.render_actions(self.blueprint.actions or {}) }
            { self.render_onstart(self.blueprint.onstart or {}) }
            { self.render_services(self.blueprint.services or {}) }

            all = [ {line_break.join(names)}];
            allAttr = {{ inherit { space.join(names) }; }};
            actionableImport = lib.attrsets.filterAttrs (n: v: v ? isSS && v.isSS) {{ inherit {SPACE.join(included_imports)}; }};

            unitsProfile = lib.attrsets.mapAttrs
                (name: unit:
                    {{
                        path = unit;
                        {LINE_BREAK.join(
                            [
                                f'{key} = if unit ? {key} && unit.{key} != null then unit.{key} else {{}};'
                                for key in list(filter(lambda x: x.__str__ != 'source' and not x.startswith('_'), schema.units.__dict__.keys()))
                            ]
                        )}
                    }}
                ) allAttr;

            currentProfile = {{
                 {self.blueprint.name} = {{
                     inherit actions;
                     inherit onstart;
                     inherit services;
                }};
            }};

            # get a json from the current configuration, units are all units defined in current ss.yaml, and
            # other configuration including onStart, actions, services
            loadProfile = pkgs.writeScriptBin "load_profile" ''
                echo '${{builtins.toJSON ( unitsProfile // currentProfile)}}'
            '';

            # get a json for all imported configurations, show their units
            loadImportUnits = pkgs.writeScriptBin "load_import_units" ''
                echo '${{
                builtins.toJSON (sslib.getUnitsFromImportedConfigures actionableImport)
                }}'
            '';

            loadImportActions = pkgs.writeScriptBin "load_import_actions" ''
                echo '${{
                builtins.toJSON (sslib.getActionsFromImportedConfigures actionableImport)
                }}'
            '';

            loadImportOnstarts = pkgs.writeScriptBin "load_import_onstarts" ''
                echo '${{
                builtins.toJSON (sslib.getOnstartFromImportedConfigures actionableImport)
                }}'
            '';

            loadImportServices = pkgs.writeScriptBin "load_import_services" ''
                echo '${{
                builtins.toJSON (sslib.getServicesFromImportedConfigures actionableImport)
                }}'
            '';

            onStartScript = sslib.onStartScript all onstart;

            startScript = ''
                export SS_PROJECT_BASE=$PWD
            '';

            funcs = [ loadProfile loadImportUnits loadImportActions loadImportOnstarts loadImportServices ];


		in {{
		inherit all allAttr funcs actions onstart services;
		scripts = builtins.concatStringsSep "\\n" [ onStartScript ];
        dependencies = all;
		}}
        { f'// {{ inherit {all_interfaces}; }}' if not self.blueprint.is_root_blueprint else '' }
	"""
