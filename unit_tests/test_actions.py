import sys
from unittest import mock
from unittest.mock import MagicMock

from test_utils import CharmTestCase

# python-apt is not installed as part of test-requirements but is imported by
# some charmhelpers modules so create a fake import.
sys.modules['apt'] = MagicMock()
sys.modules['apt_pkg'] = MagicMock()

import actions


class PauseTestCase(CharmTestCase):

    def setUp(self):
        super(PauseTestCase, self).setUp(
            actions, ["pause_unit_helper",
                      "charmhelpers.core.hookenv.log",
                      "charmhelpers.core.hookenv.status_set",
                      "charmhelpers.core.hookenv.config"])
        self.patch_object(None, "actions.register_configs",
                          name="register_configs",
                          return_value='test-config')

    def test_pauses_services(self):
        actions.pause([])
        self.pause_unit_helper.assert_called_once_with('test-config')


class ResumeTestCase(CharmTestCase):

    def setUp(self):
        super(ResumeTestCase, self).setUp(
            actions, ["resume_unit_helper",
                      "charmhelpers.core.hookenv.log",
                      "charmhelpers.core.hookenv.status_set",
                      "charmhelpers.core.hookenv.config"])
        self.patch_object(None, "actions.register_configs",
                          name="register_configs",
                          return_value='test-config')

    def test_resumes_services(self):
        actions.resume([])
        self.resume_unit_helper.assert_called_once_with('test-config')


class GetStatusTestCase(CharmTestCase):

    def setUp(self):
        super(GetStatusTestCase, self).setUp(actions, [])

    def test_clean_resource_list(self):
        data = [{"id": 1, "x": "data", "z": "data"},
                {"id": 2, "y": "data", "z": "data"}]

        clean_data = actions.clean_resource_list(data)
        for resource in clean_data:
            self.assertTrue("id" in resource)
            self.assertTrue("x" not in resource)
            self.assertTrue("y" not in resource)
            self.assertTrue("z" not in resource)

        # test allowed keys
        clean_data = actions.clean_resource_list(data,
                                                 allowed_keys=["id", "z"])
        for resource in clean_data:
            self.assertTrue("id" in resource)
            self.assertTrue("x" not in resource)
            self.assertTrue("y" not in resource)
            self.assertTrue("z" in resource)

    def test_get_resource_list_on_agents(self):
        list_function = MagicMock()
        agent_list = [{"id": 1}, {"id": 2}]
        list_results = [{"results": ["a", "b"]}, {"results": ["c"], "x": [""]}]

        expected_resource_length = 0
        for r in list_results:
            expected_resource_length += len(r.get("results", []))

        list_function.side_effect = list_results
        resource_list = actions.get_resource_list_on_agents(agent_list,
                                                            list_function,
                                                            "results")
        assert list_function.call_count > 0
        self.assertEqual(len(resource_list), expected_resource_length)

    @mock.patch("actions.function_set")
    @mock.patch("actions.get_resource_list_on_agents")
    @mock.patch("actions.get_neutron")
    def test_action_get_status(self, mock_get_neutron,
                               mock_get_resource_list_on_agents,
                               mock_function_set):
        data = [{"id": 1, "x": "data", "z": "data"},
                {"id": 2, "y": "data", "z": "data"}]
        mock_get_resource_list_on_agents.return_value = data

        clean_data = actions.clean_resource_list(data)
        yaml_clean_data = actions.format_status_output(clean_data)

        actions.get_routers(None)
        mock_function_set.assert_called_with({"router-list": yaml_clean_data})

        actions.get_dhcp_networks(None)
        mock_function_set.assert_called_with({"dhcp-networks":
                                              yaml_clean_data})

        actions.get_lbaasv2_lb(None)
        mock_function_set.assert_called_with({"load-balancers":
                                              yaml_clean_data})


class MainTestCase(CharmTestCase):

    def setUp(self):
        super(MainTestCase, self).setUp(actions, ["action_fail"])

    def test_invokes_action(self):
        dummy_calls = []

        def dummy_action(args):
            dummy_calls.append(True)

        with mock.patch.dict(actions.ACTIONS, {"foo": dummy_action}):
            actions.main(["foo"])
        self.assertEqual(dummy_calls, [True])

    def test_unknown_action(self):
        """Unknown actions aren't a traceback."""
        exit_string = actions.main(["foo"])
        self.assertEqual("Action foo undefined", exit_string)

    def test_failing_action(self):
        """Actions which traceback trigger action_fail() calls."""
        dummy_calls = []

        self.action_fail.side_effect = dummy_calls.append

        def dummy_action(args):
            raise ValueError("uh oh")

        with mock.patch.dict(actions.ACTIONS, {"foo": dummy_action}):
            actions.main(["foo"])
        self.assertEqual(dummy_calls, ["Action foo failed: uh oh"])
