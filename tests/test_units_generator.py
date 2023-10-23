from cli.configure.configure import Configure
from cli.generator.units_generator import UnitsGenerator
from .fixtures import config

class TestUnitsGenerator:
     def testSDK(self, config):
          assert UnitsGenerator(Configure(config)).generate()['#UNITS#'].replace("\n", "").replace(" ", "") == '''
          powers.db.postgres =  {
              username = "test_user"
              password = "test_password"
              database = "test_database"
              host = ""
              folder = ""
          };
      '''.replace("\n", "").replace(" ", "")

          assert UnitsGenerator(Configure(config)).generate()['#UNITS_REF#'].replace("\n", "").replace(" ", "") == '''
          [ powers.db.postgres ]
      '''.replace("\n", "").replace(" ", "")