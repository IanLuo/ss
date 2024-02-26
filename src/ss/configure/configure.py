from dataclasses import dataclass
from .parser import parse
from .unit import Unit
from os.path import dirname, exists
from jsonpath_ng import parser
import re
from typing import Any, Dict, Optional, List
from .functions.git_repo import GitRepo


@dataclass
class Source:
    name: str
    value: str

@dataclass
class UnitInstance:
    source: Source
    definition: Unit
@dataclass
class Metadata:
    name: str
    version: str
    description: str

class Configure:
    root: str
    sources: Dict[str, Source]
    metadata: Metadata
    all_unit_instances: List[UnitInstance]
    raw_config: Dict[str, Any]

    '''
    Public methods
    '''

    def __init__(self, config_path):
        self.root = dirname(config_path)

        if not exists(config_path):
            raise Exception(f"config file not existed: {config_path}")

        self._resolve_config(config_path)


    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def dict(self) -> Dict[str, Any]:
        return self.raw_config

    def units_for_source(self, source_name: str) -> List[UnitInstance]:
        return [ unit for unit in self.all_unit_instances if unit.source.name == source_name ]

    def unit_from_source(self, source_name: str, unit_name: str) -> Optional[UnitInstance]:
        return next(unit for unit in self.units_for_source(source_name) if unit.definition.name == unit_name)

    '''
    Private methods
    '''

    def _resolve_config(self, config_path: str):
        with open(config_path, 'r') as f:
            yaml = f.read()

            temp_config = parse(yaml)

            if temp_config == None:
                raise Exception(f"config file is empty: {config_path}")

            self.sources = self._read_source(temp_config)
            # read metadata
            self.metadata = self._read_metadata(temp_config)

        # reparse the yaml after all vars are resolved
        temp_config = parse(self._resolve_vars(config_str=yaml))

        self.raw_config = self._resolve_functions(temp_config)

        # read units
        self.all_unit_instances = self._find_units(config=self.raw_config)

    def _read_source(self, config: Dict[str, Any]) -> Dict[str, Source]:
        sources = config['source']
        return { name: Source(name, value) for name, value in sources.items() }

    def _read_metadata(self, parsed_config):
        metadata = parsed_config['metadata']
        return Metadata(
            metadata['name'],
            metadata['version'],
            metadata['description']
        )

    def _resolve_vars(self, config_str: str) -> str:
        '''firest to find the first variable, replace the variable with json value, use the result as parameter, and then continue with next variable, and goon'''

        pattern = r'(\$[\w\>\_]+\.?)+'
        first_match = re.search(pattern, config_str)
        if first_match is None:
            return config_str
        else:
            var_name = first_match.group(1) or ''
            real_var_name = var_name.replace('>', '.').replace('$', '')
            var_value = self._find_value(real_var_name, parse(config_str))
            new_config = config_str.replace(var_name, str(var_value))
            return self._resolve_vars(new_config)

    def _resolve_functions(self, config: Dict[str, Any]) -> dict:
        '''Functions are resolved by each function provider, then will be generated into nix function as a result'''
        pattern = r'(\^\w+)'

        def walk_dict(d, parent_dict=None, parent_key=None):
            for key, value in d.items():
                match = re.search(pattern, key)
                if match is not None:
                    function_name = match.group(1)
                    parent_dict[parent_key] = self._resolve_function_by_name(parent_dict[parent_key])
                elif isinstance(value, dict):
                    walk_dict(value, parent_dict=d, parent_key=key)

        walk_dict(config)

        return config;

    def _resolve_function_by_name(self, value: dict):
        if GitRepo.is_git_repo(value):
            return GitRepo(value)
        else: value

    def _find_value(self, key_path: str, config: dict) -> Optional[Any]:
        jsonpath_expr = parser.parse(key_path)
        result = jsonpath_expr.find(config)

        if len(result) == 0:
            return None

        return result[0].value

    def _find_units(self, config: dict) -> list[UnitInstance]:
        return [ UnitInstance(source, Unit(name=unit_name, params=params))
            for source_name, source in self.sources.items()
                for unit_name, params in (config[source_name] or {}).items() ]
