import sys
from uuid import uuid4
import yaml

from oslo_config import cfg
from oslo_log import log

from heat.common import context as hcontext
from heat.db import api as db_api

from heat.objects import fields as heat_fields
from heat.objects.raw_template import RawTemplate
from heat.objects.resource import Resource
from heat.objects.resource_data import ResourceData
from heat.objects.stack import Stack

from neutron import context as ncontext

import neutron.db.api as ndbapi
from neutron_lbaas.db.loadbalancer.models import HealthMonitorV2
from neutron_lbaas.db.loadbalancer.models import Listener
from neutron_lbaas.db.loadbalancer.models import LoadBalancer
from neutron_lbaas.db.loadbalancer.models import MemberV2
from neutron_lbaas.db.loadbalancer.models import PoolV2


CONF = cfg.CONF


class Context(object):

    _neutron_context = None
    _heat_context = None
    _current_context = None

    @classmethod
    def get_neutron_context(cls):
        if (not cls._neutron_context or
                cls._current_context != cls._neutron_context):
            try:
                default_config_files = cfg.find_config_files('neutron')
                CONF(sys.argv[1:], project='neutron', prog='lbaas-upgrade',
                     default_config_files=default_config_files)
            except RuntimeError as e:
                sys.exit("ERROR: %s" % e)

            cls._neutron_context = ncontext.get_admin_context()
            cls._current_context = cls._neutron_context

        return cls._neutron_context

    @classmethod
    def get_heat_context(cls):
        if (not cls._heat_context or
                cls._current_context != cls._heat_context):
            try:
                default_config_files = cfg.find_config_files('heat')
                CONF(sys.argv[1:], project='heat', prog='lbaas-upgrade',
                     default_config_files=default_config_files)
            except RuntimeError as e:
                sys.exit("ERROR: %s" % e)

            cls._heat_context = hcontext.get_admin_context()
            cls._current_context = cls._heat_context

        return cls._heat_context

# TODO(ctxt) this is really, really ugly, fix it!
hctxt = Context.get_heat_context
nctxt = Context.get_neutron_context


V1_RESOURCES = {
    'OS::Neutron::HealthMonitor': 'OS::Neutron::LBaaS::HealthMonitor',
    'OS::Neutron::PoolMember': 'OS::Neutron::LBaaS::PoolMember',
    'OS::Neutron::Pool': 'OS::Neutron::LBaaS::Pool',
    'OS::Neutron::LoadBalancer': 'OS::Neutron::LBaaS::LoadBalancer'
}

V2_RESOURCES = [
    'OS::Neutron::LBaaS::HealthMonitor',
    'OS::Neutron::LBaaS::PoolMember',
    'OS::Neutron::LBaaS::Pool',
    'OS::Neutron::LBaaS::Listener',
    'OS::Neutron::LBaaS::LoadBalancer'
]

V1_REQUIRED_PROPERTIES = {
    'OS::Neutron::HealthMonitor': ['delay', 'type', 'max_retries', 'timeout'],
    'OS::Neutron::PoolMember': ['pool_id', 'address', 'protocol_port'],
    'OS::Neutron::Pool': ['protocol', 'subnet', 'lb_method', 'vip'],
    'OS::Neutron::LoadBalancer': ['pool_id', 'protocol_port'],
}

V1_OPTIONAL_PROPERTIES = {
    'OS::Neutron::HealthMonitor': ['admin_state_up', 'http_method', 'expected_codes', 'url_path'],
    'OS::Neutron::PoolMember': ['weight', 'admin_state_up'],
    'OS::Neutron::Pool': ['name', 'description', 'admin_state_up', 'provider', 'monitors'],
    'OS::Neutron::LoadBalancer': ['members'],
}

V2_REQUIRED_PROPERTIES = {
    'OS::Neutron::LBaaS::HealthMonitor': ['pool', 'delay', 'type',
                                          'max_retries', 'timeout'],
    'OS::Neutron::LBaaS::PoolMember': ['pool', 'address', 'protocol_port'],
    'OS::Neutron::LBaaS::Pool': ['listener', 'protocol', 'lb_algorithm'],
    'OS::Neutron::LBaaS::LoadBalancer': ['vip_subnet'],
    'OS::Neutron::LBaaS::Listener': ['protocol',
                                     'protocol_port', 'loadbalancer'],
}

PROP_V1_DEL = {
    'PoolMember': ['pool_id'],
    'Pool': ['subnet', 'lb_method', 'provider', 'vip', 'monitors'],
    'LoadBalancer': ['pool_id', 'protocol_port', 'members'],
}


class LBaaSv2Data(object):

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(LBaaSv2Data, cls).__new__(cls)
        return cls.instance

    def __init__(self):
            self.__load_health_monitors()
            self.__load_pool_members()
            self.__load_pools()
            self.__load_load_balancers()
            self.__load_listeners()

    def get_health_monitor(self, id):
        return self.__hm_dict.get(id, None)

    def get_pool_member(self, id):
        return self.__pm_dict.get(
            id,
            self.__pm_dict['pool_id'].get(id, None))

    def get_pool(self, id):
        return self.__p_dict.get(
            id,
            self.__p_dict['healthmonitor_id'].get(id, None))

    def get_load_balancer(self, id):
        return self.__lb_dict.get(id, None)

    def get_load_balancer_from_listener(self, id):
        l_obj = self.__l_dict.get(id, None)
        if l_obj:
            return self.get_load_balancer(l_obj.loadbalancer_id)
        return None

    def get_listener(self, id):
        return self.__l_dict.get(
            id,
            self.__l_dict['pool_id'].get(id, None))

    def __load_health_monitors(self):
        if (not hasattr(self, '__hm_dict') or not self.__hm_dict):
            hm_lst = ndbapi.get_objects(nctxt(), HealthMonitorV2)
            self.__hm_dict = {hm_res.id: hm_res for hm_res in hm_lst}

    def __load_pool_members(self):
        if (not hasattr(self, '__pm_dict') or not self.__pm_dict):
            pm_lst = ndbapi.get_objects(nctxt(), MemberV2)
            self.__pm_dict = {pm_res.id: pm_res for pm_res in pm_lst}
            self.__pm_dict['pool_id'] = {
                pm_res.pool_id: pm_res for pm_res in pm_lst}

    def __load_pools(self):
        if (not hasattr(self, '__p_dict') or not self.__p_dict):
            p_lst = ndbapi.get_objects(nctxt(), PoolV2)
            self.__p_dict = {p_res.id: p_res for p_res in p_lst}
            self.__p_dict['healthmonitor_id'] = {
                p_res.healthmonitor_id: p_res for p_res in p_lst}

    def __load_load_balancers(self):
        if (not hasattr(self, '__lb_dict') or not self.__lb_dict):
            lb_lst = ndbapi.get_objects(nctxt(), LoadBalancer)
            self.__lb_dict = {lb_res.id: lb_res for lb_res in lb_lst}

    def __load_listeners(self):
        if (not hasattr(self, '__l_dict') or not self.__l_dict):
            l_lst = ndbapi.get_objects(nctxt(), Listener)
            self.__l_dict = {l_res.id: l_res for l_res in l_lst}
            self.__l_dict['pool_id'] = {
                l_res.default_pool_id: l_res for l_res in l_lst}


class StackHandler(object):

    def __init__(self):
        self.lbaasv2_data = LBaaSv2Data()
        self.stack_lst = self.get_lbv1_stacks()

    def translate_all_stacks(self):
        for stack in self.stack_lst:
            res_h = ResourceHandler(stack.id, self.lbaasv2_data)
            res_h.translate_resources()

            temp_h = TemplateHandler(stack.raw_template_id, res_h, self.lbaasv2_data)
            temp_h.translate_template()

    def get_lbv1_stacks(self):
        stack_lst = list()
        stack_lst_all = Stack.get_all(hctxt(), show_nested=True, tenant_safe=False, show_hidden=True)

        for stack in stack_lst_all:
            if stack.action == 'DELETE' and stack.status == 'COMPLETE':
                continue
            raw_temp = RawTemplate.get_by_id(hctxt(), stack.raw_template_id)
            if any(r in str(raw_temp.template) for r in V1_RESOURCES.keys()):
                stack_lst.append(stack)

        return stack_lst


class ResourceHandler(object):

    def __init__(self, stack_id, lbaasv2_data):
        self.lbaasv2_data = lbaasv2_data
        self.res_dict = self._get_active_lb_resources(stack_id)
        # lb_res_name -> lbaas_loadbalancer.id
        self._lb_id = dict()
        self._stack_id = stack_id

    def translate_resources(self):
        print("Translating stack {}".format(self._stack_id))
        for res_type, res_dict in dict(self.res_dict).items():
            for res_name, res in res_dict.items():
                print("Translating {}: {}".format(res_type, res_name))
                if res_type == 'HealthMonitor':
                    self._translate_health_monitor(res)
                if res_type == 'PoolMember':
                    self._translate_pool_member(res)
                if res_type == 'LoadBalancer':
                    self._translate_load_balancer(res)
                if res_type == 'Pool':
                    self._translate_pool(res)
                    self._handle_no_lb_case(res)
                    self._create_listener(res)
        self._finalize_and_save()

    def _get_active_lb_resources(self, stack_id):
        """
        Return dictionary of all lbaas v1 relevant resources.
        Ex.:
         res_dict['PoolMember']['server1'] = ResourceX
         res_dict['PoolMember']['server2'] = ResourceY
        """
        resources_all = Resource.get_all_by_stack(hctxt(), stack_id)
        res_dict = dict()

        for res_id, res in resources_all.items():
            if not res.properties_data:
                continue
            res_prop_set = set(res.properties_data.keys())
            for res_type, req_properties in V1_REQUIRED_PROPERTIES.items():
                req_prop_set = set(req_properties)
                opt_prop_set = set(V1_OPTIONAL_PROPERTIES[res_type])

                if res_prop_set.issuperset(req_prop_set):
                    diff_set = res_prop_set.difference(req_prop_set)

                    if diff_set.issubset(opt_prop_set):
                        res_type_short = res_type.split('::')[-1]
                        if res_type_short not in res_dict:
                            res_dict[res_type_short] = dict()

                        res_dict[res_type_short][res.name] = res

        return res_dict

    def _translate_health_monitor(self, hm_res):
        """
        In v2 health monitor has 'pool' mandatory property (1-1 relationship)
        and tenant_id which can be ignored since it's not mandatory.
        Invariants and constraints:
        * we only have pools with at most 1 health monitor,
        * translate iff #health monitors <= #pools,
        * in other case set nova_instance to null for safety.
        """
        hm_properties = hm_res.properties_data

        if ('Pool' in self.res_dict and
            len(self.res_dict['HealthMonitor']) <= len(self.res_dict['Pool'])):
            hm_nova_instance = hm_res.nova_instance
            # hm_res.name = 'tcp_pool'
            lbaas_pool = self.lbaasv2_data.get_pool(hm_nova_instance)
            if lbaas_pool:
                assert hm_nova_instance == lbaas_pool.healthmonitor_id
                hm_properties['pool'] = lbaas_pool.id
            else:
                # health monitor is not used anywhere
                # TODO: should we rmove this guys?
                print("No pool associated with hm: {}".format(hm_res.name))
                hm_res.nova_instance = None
        else:
            print("No pools in this template, hm: {}".format(hm_res.name))
            hm_res.nova_instance = None

    def _translate_pool_member(self, pm_res):
        """
        In v2 'pool' property is equivalent to v1's 'pool_id' property.
        Property 'subnet' is new but non-mandatory so we can ignore it.
        """
        pm_properties = pm_res.properties_data
        pm_properties['pool'] = pm_properties['pool_id']

    def _translate_pool(self, p_res):
        """
        Property 'lb_method' was renamed to 'lb_algorithm' and 'listener'
        property is added as lbaas v2 introduced this object.
        Invariant: lb pool has 0 or 1 health monitor.
        If pool heat resource has monitors property, we handle it:
        * "get_resource's" hm is active one:
        * - if we have multiple get_resources, remove non-active ones,
        * - if we only have one, no work needed;
        * active ~ uuid => we generate heat resource and update template.
        """
        p_properties = p_res.properties_data
        p_properties['lb_algorithm'] = p_properties['lb_method']
        p_properties['listener'] = (
            self.lbaasv2_data.get_listener(p_res.nova_instance).id
        )

        def create_health_monitor(hm_obj):
            hm_res_values = dict()
            attr_name_lst = [
                'created_at', 'updated_at', 'action', 'status',
                'status_reason', 'stack_id', 'engine_id', 'atomic_key',
                'current_template_id', 'root_stack_id'
            ]
            for attr in attr_name_lst:
                hm_res_values[attr] = getattr(p_res, attr)

            hm_res_name = "{}HM".format(p_res.name)
            hm_res_values['nova_instance'] = hm_obj.id
            hm_res_values['name'] = hm_res_name
            hm_res_values['rsrc_metadata'] = {}
            hm_res_values['properties_data'] = {}
            hm_res_values['uuid'] = uuid4().hex
            hm_res_values['id'] = None
            hm_res_values['needed_by'] = []
            hm_res_values['requires'] = []
            hm_res_values['replaces'] = None
            hm_res_values['replaced_by'] = None
            hm_res_values['properties_data_encrypted'] = 0

            hm_res_pd = dict()
            # TODO: session persistance
            hm_res_pd["delay"] = hm_obj.delay
            hm_res_pd["type"] = hm_obj.type
            hm_res_pd["max_retries"] = hm_obj.max_retries
            hm_res_pd["timeout"] = hm_obj.timeout
            hm_res_pd["pool"] = hm_obj.pool
            hm_res_values['properties_data'] = hm_res_pd

            hm_res = Resource.create(hctxt(), hm_res_values)
            if 'HealthMonitor' not in self.res_dict:
                self.res_dict['HealthMonitor'] = dict()
            self.res_dict['HealthMonitor'][hm_res_name] = hm_res

        def delete_health_monitor(hm_res_name, hm_res):
            Resource.delete(hctxt(), hm_res.id)
            self.res_dict['HealhMonitor'].pop(hm_res_name)

        if 'monitors' in p_properties:
            p_obj = self.lbaasv2_data.get_pool(p_res.nova_instance)
            # this is the only used hm after the data migration
            active_hm_id = p_obj.healthmonitor_id

            for mon in p_properties['monitors']:
                if isinstance(mon, str):
                    hm_obj = self.lbaasv2_data.get_health_monitor(
                        p_obj.healthmonitor_id)
                    if hm_obj.id == active_hm_id:
                        create_health_monitor(hm_obj)
                elif isinstance(mon, dict) and 'get_resource' in mon:
                    hm_res_name = mon['get_resource']
                    hm_res = self.res_dict['HealthMonitor'][hm_res_name]
                    if hm_res.nova_instance != active_hm_id:
                        delete_health_monitor(hm_res_name, hm_res)

    def _handle_no_lb_case(self, p_res):
        def respective_lb_res_exists():
            if 'LoadBalancer' in self.res_dict:
                for _, lb_res in self.res_dict['LoadBalancer'].items():
                    lb_res_pool_id = lb_res.properties_data['pool_id']
                    if lb_res_pool_id == p_res.nova_instance:
                        return True
            return False

        if not respective_lb_res_exists():
           self._create_load_balancer(p_res)

    def _create_load_balancer(self, p_res):
        """
        In case I have only pool created in v1, I need to create load balancer
        before the listener gets created because listener requires load balancer.
        Invariants:
        * this implies we are using PoolMember resources.
        """
        l_obj = self.lbaasv2_data.get_listener(p_res.nova_instance)
        lb_obj = self.lbaasv2_data.get_load_balancer(l_obj.loadbalancer_id)

        lb_res_values = dict()
        attr_name_lst = [
            'created_at', 'updated_at', 'action', 'status',
            'status_reason', 'stack_id', 'engine_id', 'atomic_key',
            'current_template_id', 'root_stack_id'
        ]
        for attr in attr_name_lst:
            lb_res_values[attr] = getattr(p_res, attr)

        lb_res_name = "{}LB".format(p_res.name)
        lb_res_values['nova_instance'] = lb_obj.id
        lb_res_values['name'] = lb_res_name
        lb_res_values['rsrc_metadata'] = {}
        lb_res_values['properties_data'] = {}
        lb_res_values['uuid'] = uuid4().hex
        lb_res_values['id'] = None
        lb_res_values['needed_by'] = []
        lb_res_values['requires'] = []
        lb_res_values['replaces'] = None
        lb_res_values['replaced_by'] = None
        lb_res_values['properties_data_encrypted'] = 0

        lb_res_pd = dict()
        lb_res_pd["name"] = lb_obj.name
        lb_res_pd["description"] = lb_obj.description
        lb_res_pd["vip_address"] = lb_obj.vip_address
        lb_res_pd["vip_subnet"] = lb_obj.vip_subnet_id
        lb_res_values['properties_data'] = lb_res_pd

        lb_res = Resource.create(hctxt(), lb_res_values)
        if 'LoadBalancer' not in self.res_dict:
            self.res_dict['LoadBalancer'] = dict()
        self.res_dict['LoadBalancer'][lb_res_name] = lb_res
        self._lb_id[lb_res.name] = lb_obj.id

    def _translate_load_balancer(self, lb_res):
        lb_properties = lb_res.properties_data

        pool_id = lb_properties['pool_id']
        l_obj = self.lbaasv2_data.get_listener(pool_id)
        lb_obj = self.lbaasv2_data.get_load_balancer(l_obj.loadbalancer_id)

        lb_properties['name'] = lb_obj.name
        lb_properties['description'] = lb_obj.description
        lb_properties['vip_subnet'] = lb_obj.vip_subnet_id
        lb_properties['vip_address'] = lb_obj.vip_address

        self._lb_id[lb_res.name] = lb_obj.id

        if 'members' in lb_res.properties_data:
            for member in lb_res.properties_data['members']:
                protocol_port = lb_properties['protocol_port']
                self._create_pool_member(
                    pool_id, protocol_port, member, lb_res)

    def _create_pool_member(self, pool_id, protocol_port, member, lb_res):
        pm_res_values = dict()
        attr_name_lst = [
            'created_at', 'updated_at', 'action', 'status',
            'status_reason', 'stack_id', 'engine_id', 'atomic_key',
            'current_template_id', 'root_stack_id'
        ]
        for attr in attr_name_lst:
            pm_res_values[attr] = getattr(lb_res, attr)

        #server_res = Resource.get_by_name_and_stack(
        #    hctxt(), member_res_name, self._stack_id)
        server_res = None
        all_res = Resource.get_all_by_stack(
            hctxt(),
            self._stack_id
        )
        for res_name, res in all_res.items():
            if res.nova_instance == member:
                server_res = res

        pm_res_data = ResourceData.get_by_key(
            hctxt(), lb_res.id, server_res.nova_instance)
        pm_id = pm_res_data.value
        # XXX: no delete, cascade delete takes care of this
        #ResourceData.delete(server_res, server_res.nova_instance)
        pm_obj = self.lbaasv2_data.get_pool_member(pm_id)

        pm_res_name = "{}PM".format(server_res.name)
        pm_res_values['nova_instance'] = pm_obj.id
        pm_res_values['name'] = pm_res_name
        pm_res_values['rsrc_metadata'] = {}
        pm_res_values['properties_data'] = {}
        pm_res_values['uuid'] = uuid4().hex
        pm_res_values['id'] = None
        pm_res_values['needed_by'] = []
        pm_res_values['requires'] = []
        pm_res_values['replaces'] = None
        pm_res_values['replaced_by'] = None
        pm_res_values['properties_data_encrypted'] = 0

        pm_res_pd = dict()
        pm_res_pd["pool"] = pm_obj.pool_id
        pm_res_pd["address"] = pm_obj.address
        pm_res_pd["protocol_port"] = pm_obj.protocol_port
        pm_res_values['properties_data'] = pm_res_pd

        pm_res = Resource.create(hctxt(), pm_res_values)
        if 'PoolMember' not in self.res_dict:
            self.res_dict['PoolMember'] = dict()
        self.res_dict['PoolMember'][pm_res_name] = pm_res

    def _create_listener(self, p_res):
        l_obj = self.lbaasv2_data.get_listener(p_res.nova_instance)

        l_res_values = dict()
        attr_name_lst = [
            'created_at', 'updated_at', 'action', 'status',
            'status_reason', 'stack_id', 'engine_id', 'atomic_key',
            'current_template_id', 'root_stack_id'
        ]
        for attr in attr_name_lst:
            l_res_values[attr] = getattr(p_res, attr)

        listener_name = "{}Listener1".format(p_res.name)
        l_res_values['nova_instance'] = l_obj.id
        l_res_values['name'] = listener_name
        l_res_values['rsrc_metadata'] = {}
        l_res_values['properties_data'] = {}
        l_res_values['uuid'] = uuid4().hex
        l_res_values['id'] = None
        l_res_values['needed_by'] = []
        l_res_values['requires'] = []
        l_res_values['replaces'] = None
        l_res_values['replaced_by'] = None
        l_res_values['properties_data_encrypted'] = 0

        l_res_pd = dict()
        l_res_pd["protocol"] = l_obj.protocol
        l_res_pd["protocol_port"] = l_obj.protocol_port
        l_res_pd["loadbalancer"] = l_obj.loadbalancer_id
        l_res_pd["name"] = l_obj.name
        l_res_pd["description"] = l_obj.description
        l_res_values['properties_data'] = l_res_pd

        l_res = Resource.create(hctxt(), l_res_values)
        if 'Listener' not in self.res_dict:
            self.res_dict['Listener'] = dict()
        self.res_dict['Listener'][listener_name] = l_res

    def _finalize_and_save(self):
        for res_type, prop_list in PROP_V1_DEL.items():
            if res_type in self.res_dict:
                for prop in prop_list:
                    for res_name, res in self.res_dict[res_type].items():
                        res.properties_data.pop(prop, None)

        for res_type, res_dict in self.res_dict.items():
            for res_name, res in res_dict.items():
                res.update_and_save(
                    {'properties_data': res.properties_data})

                if res_type == 'LoadBalancer':
                    res.update_and_save(
                        {'nova_instance': self._lb_id[res_name]})
                elif res_type == 'HealthMonitor' and not res.nova_instance:
                    res.update_and_save(
                        {'nova_instance': None})

    def get_resource_prop_name(self, res_type, nova_instance):
        for res_name, res in self.res_dict[res_type].items():
            if res.nova_instance == nova_instance:
                return res.name
        return None

    def get_resource_name(self, res_type, nova_instance):
        for res_name, res in self.res_dict[res_type].items():
            if res.nova_instance == nova_instance:
                return res_name
        return None

class TemplateHandler(object):

    def __init__(self, template_id, res_handler, lbaasv2_data):
        self.res_handler = res_handler
        self.res_dict = res_handler.res_dict
        self.raw_template = RawTemplate.get_by_id(hctxt(), template_id)
        self.template = self.raw_template.template
        self.resources = self.template['resources']
        self.lbaasv2_data = lbaasv2_data
        self._template_id = template_id

    def translate_template(self):
        print("Translating template {}".format(self._template_id))
        t_res_dict = {
            res_name: res_prop for res_name, res_prop in self.resources.items()
            if res_prop['type'] in V1_RESOURCES
        }

        self._sync_health_monitors(t_res_dict)
        self._sync_load_balancers()

        for res_name, res in t_res_dict.items():
            if res['type'].split('::')[-1] == 'HealthMonitor':
                self._translate_health_monitor(res_name, res)
            if res['type'].split('::')[-1] == 'PoolMember':
                self._translate_pool_member(res_name, res)
            if res['type'].split('::')[-1] == 'LoadBalancer':
                self._translate_load_balancer(res_name, res)
            if res['type'].split('::')[-1] == 'Pool':
                self._translate_pool(res_name, res)
                self._create_listener(res_name, res)

        self._handle_vip_properties()
        self._finalize_and_save()

    def _sync_health_monitors(self, t_res_dict):

        def create_health_monitor(hm_res_name):
            hm_res_p = (
                self.res_dict['HealthMonitor'][hm_res_name].properties_data
            )
            t_hm_res_p = dict()
            t_hm_res_p['delay'] = hm_res_p['delay']
            t_hm_res_p['type'] = hm_res_p['type']
            t_hm_res_p['max_retries'] = hm_res_p['max_retries']
            t_hm_res_p['timeout'] = hm_res_p['timeout']
            #TODO: test again!
            t_hm_res_p['pool'] = {
                'get_resource':
                self.res_handler.get_resource_name(
                    'Pool',
                    hm_res_p['pool']
                )
            }
            self.resources[hm_res_name] = dict()
            self.resources[hm_res_name]['properties'] = t_hm_res_p
            self.resources[hm_res_name]['type'] = (
                'OS::Neutron::LBaaS::HealthMonitor'
            )

        def delete_health_monitor(hm_res_name):
            t_res_dict.pop(hm_res_name)
            self.resources.pop(hm_res_name)

        s_hm_res_lst = [
            hm_r_name for hm_r_name in self.res_dict.get('HealthMonitor', [])
        ]
        t_hm_res_lst = [
            r_n for r_n, r_p in self.resources.items()
            if r_p['type'] == 'OS::Neutron::HealthMonitor'
        ]

        for hm_res_name in set(t_hm_res_lst).difference(set(s_hm_res_lst)):
            delete_health_monitor(hm_res_name)

        for hm_res_name in set(s_hm_res_lst).difference(set(t_hm_res_lst)):
            create_health_monitor(hm_res_name)


    def _sync_load_balancers(self):

        def create_load_balancer(lb_res_name):
            lb_res_p = (
                self.res_dict['LoadBalancer'][lb_res_name].properties_data
            )
            t_lb_res_p = dict()
            t_lb_res_p['name'] = lb_res_p['name']
            t_lb_res_p['description'] = lb_res_p['description']
            t_lb_res_p['vip_address'] = lb_res_p['vip_address']
            t_lb_res_p['vip_subnet'] = lb_res_p['vip_subnet']

            self.resources[lb_res_name] = dict()
            self.resources[lb_res_name]['properties'] = t_lb_res_p
            self.resources[lb_res_name]['type'] = (
                'OS::Neutron::LBaaS::LoadBalancer'
            )

        s_lb_res_lst = [
            lb_r_name for lb_r_name in self.res_dict.get('LoadBalancer', [])
        ]
        t_lb_res_lst = [
            lb_n for lb_n, lb_p in self.resources.items()
            if lb_p['type'] == 'OS::Neutron::LoadBalancer'
        ]

        for lb_res_name in set(s_lb_res_lst).difference(set(t_lb_res_lst)):
            create_load_balancer(lb_res_name)

    def _handle_vip_properties(self):
        """
        Handle translation of references to vip's properties (address and port_id)
        """

        def get_pool_vip_address_list(output_vip_list, output_dict):
            for output_name, output_value in output_dict.items():
                if isinstance(output_value, list):
                    if 'vip' in output_value and 'address' in output_value:
                        output_vip_list.append(output_value)
                elif isinstance(output_value, dict):
                    get_pool_vip_address_list(output_vip_list, output_value)

        def get_pool_vip_port_id_list(output_vip_list, output_dict):
            for output_name, output_value in output_dict.items():
                if isinstance(output_value, list):
                    if 'vip' in output_value and 'port_id' in output_value:
                        output_vip_list.append(output_value)
                elif isinstance(output_value, dict):
                    get_pool_vip_port_id_list(output_vip_list, output_value)

        def translate_pool_vip_address(res_dict):
            """
            vip_address: {get_attr: [pool, vip, address]} ->
            vip_address: {get_attr: [loadbalancer, vip_address]}
            """
            out_vip_list = list()
            vip_address_list = get_pool_vip_address_list(
                out_vip_list, res_dict)

            for out_vip in out_vip_list:
                listener_name = "{}Listener1".format(out_vip[0])

                l_res = self.res_dict['Listener'][listener_name]
                lb_obj = self.lbaasv2_data.get_load_balancer_from_listener(
                    l_res.nova_instance)
                lb_res_name = self.res_handler.get_resource_name(
                    'LoadBalancer', lb_obj.id)

                out_vip[:] = [lb_res_name, 'vip_address']

        def translate_pool_port_id(res_dict):
            """
            port_id: {get_attr: [pool, vip, port_id]} ->
            port_id: {get_attr: [loadbalancer, vip_port_id]}
            """
            out_vip_list = list()
            port_id_list = get_pool_vip_port_id_list(
                out_vip_list, res_dict)

            for out_vip in out_vip_list:
                listener_name = "{}Listener1".format(out_vip[0])

                l_res = self.res_dict['Listener'][listener_name]
                lb_obj = self.lbaasv2_data.get_load_balancer_from_listener(
                    l_res.nova_instance)
                lb_res_name = self.res_handler.get_resource_name(
                    'LoadBalancer', lb_obj.id)

                out_vip[:] = [lb_res_name, 'vip_port_id']

        if 'outputs' in self.template:
            translate_pool_vip_address(self.template['outputs'])
        translate_pool_vip_address(self.resources)
        translate_pool_port_id(self.resources)

    def _translate_health_monitor(self, res_name, res):
        """
        In v2 health monitor has to have corresponding pool.
        In case we have a pool in the stack, we set it on the health monitor.
        """

        def get_hm_res():
            for hm_name, hm_res in self.res_dict['HealthMonitor'].items():
                if hm_name == res_name:
                    return hm_res
            return None

        res['type'] = V1_RESOURCES[res['type']]
        if 'Pool' in self.res_dict:
            hm_res = get_hm_res()
            assert hm_res != None and hm_res.nova_instance != None
            p_obj = self.lbaasv2_data.get_pool(hm_res.nova_instance)
            pool_name = self.res_handler.get_resource_prop_name(
                'Pool', p_obj.id)

            if pool_name:
                res['properties']['pool'] = { 'get_resource': pool_name }

    def _translate_pool_member(self, res_name, res):
        """
        In v2 'pool' property is equivalent to v1's 'pool_id' property.
        Property 'subnet' is new but non-mandatory so we can ignore it.
        """
        res['type'] = V1_RESOURCES[res['type']]
        res['properties']['pool'] = res['properties'].pop('pool_id')

    def _translate_pool(self, res_name, res):
        """
        Important properties to set are 'lb_algorithm', 'protocol' and 'listener'.
        """

        def get_pool_res():
            for name, pool_res in self.res_dict['Pool'].items():
                if name == res_name:
                    return pool_res
            return None

        pool_res = get_pool_res()
        assert pool_res != None
        listener_name = "{}Listener1".format(pool_res.name)

        res['type'] = V1_RESOURCES[res['type']]
        res['properties']['lb_algorithm'] = (
            pool_res.properties_data['lb_algorithm']
        )
        res['properties']['protocol'] = (
            pool_res.properties_data['protocol']
        )
        res['properties']['listener'] = {
            'get_resource':
            listener_name
        }
        res['properties'].pop('subnet', None)
        res['properties'].pop('lb_method', None)
        res['properties'].pop('admin_state_up', None)
        res['properties'].pop('provider', None)
        res['properties'].pop('vip', None)
        res['properties'].pop('monitors', None)

    def _translate_load_balancer(self, res_name, res):
        """
        Mandatory property is 'vip_subnet'.
        """

        def get_load_balancer_res():
            for lb_name, lb_res in self.res_dict['LoadBalancer'].items():
                if lb_name == res_name:
                    return lb_res
            return None

        def create_pool_member(pm_res_name):
            pm_res = self.res_dict['PoolMember'][pm_res_name]
            pool_res_name = self.res_handler.get_resource_name(
                'Pool', pm_res.properties_data['pool'])

            pm_res_p = dict()
            pm_res_p['pool'] = {'get_resource': pool_res_name}
            pm_res_p['address'] = {'get_attr': [pm_res_name[:-2], 'first_address']}
            pm_res_p['protocol_port'] = pm_res.properties_data['protocol_port']

            self.resources[pm_res_name] = dict()
            self.resources[pm_res_name]['properties'] = pm_res_p
            self.resources[pm_res_name]['type'] = (
                'OS::Neutron::LBaaS::PoolMember'
            )

        lb_res = get_load_balancer_res()
        assert lb_res != None

        res['type'] = V1_RESOURCES[res['type']]
        res['properties']['vip_subnet'] = (
            lb_res.properties_data['vip_subnet']  # XXX: subnet id
        )
        if 'name' in lb_res.properties_data:
            res['properties']['name'] = (
                lb_res.properties_data['name']
            )
        if 'description' in lb_res.properties_data:
            res['properties']['description'] = (
                lb_res.properties_data['description']
            )
        if 'vip_address' in lb_res.properties_data:
            res['properties']['vip_address'] = (
                lb_res.properties_data['vip_address']
            )

        res['properties'].pop('pool_id', None)
        res['properties'].pop('protocol_port', None)

        if 'members' in res['properties']:
            for member in res['properties']['members']:
                if 'get_resource' in member:
                    pm_res_name = "{}PM".format(member['get_resource'])
                    create_pool_member(pm_res_name)
            res['properties'].pop('members')

    def _create_listener(self, pool_res_name, pool_res):
        listener_name = "{}Listener1".format(pool_res_name)
        l_res = self.res_dict['Listener'][listener_name]
        l_res_p = dict()
        l_res_p['name'] = l_res.properties_data['name']
        l_res_p['description'] = l_res.properties_data['description']
        l_res_p['protocol'] = l_res.properties_data['protocol']
        l_res_p['protocol_port'] = l_res.properties_data['protocol_port']
        l_res_p['loadbalancer'] = {
            'get_resource':
            self.res_handler.get_resource_name(
                'LoadBalancer',
                l_res.properties_data['loadbalancer']
            )
        }

        self.resources[l_res.name] = dict()
        self.resources[l_res.name]['type'] = 'OS::Neutron::LBaaS::Listener'
        self.resources[l_res.name]['properties'] = l_res_p

    def _finalize_and_save(self):
        # print(yaml.safe_dump(self.template, indent=2))
        RawTemplate.update_by_id(
            hctxt(),
            self.raw_template.id,
            {'template': self.template}
        )

def main():
    stack_h = StackHandler()
    stack_h.translate_all_stacks()

if __name__ == "__main__":
    main()
