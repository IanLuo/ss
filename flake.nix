{
  description = "A very basic flake";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.nixpkgs.inputs.nixpkgs.follows = "nixpkgs";

  inputs.flake-utils.url = "github:numtide/flake-utils";

  inputs.sstemplate.url = "git+file:///Users/ianluo/Documents/apps/templates";
  inputs.sstemplate.inputs.nixpkgs.follows = "nixpkgs";

  outputs = { self, nixpkgs, flake-utils, sstemplate }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        version = "0.0.1";
        name = "ss-cli";

        units = pkgs.callPackage ./units.nix { inherit sstemplate name version system; };

        update-template = pkgs.writeScriptBin "update_template" ''
          nix flake lock --update-input devne-template
        '';
      in
      {
        devShells = with pkgs; {
          default = mkShell {
            name = name;
            version = version;
            buildInputs = units.all ++ [
              update-template
            ]; 

            shellHook = ''
              ${units.scripts}
            '';
          };
        };

        packages = units.packages;
      });
}