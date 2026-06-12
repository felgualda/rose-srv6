#!/usr/bin/python

# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring

import os
import shutil
import sys
from argparse import ArgumentParser

import python_hosts
from dotenv import load_dotenv
from mininet.cli import CLI
# from mininet.link import Link
from mininet.log import setLogLevel
from mininet.net import Mininet
# from mininet.topo import Topo
from mininet.node import Host
from mininet.util import dumpNodeConnections

# BASEDIR = "/home/user/mytests/ospf3routers/nodeconf/"
BASEDIR = os.getcwd() + "/nodeconf/"
OUTPUT_PID_TABLE_FILE = "/tmp/pid_table_file.txt"

PRIVDIR = '/var/priv'

# Path of the file containing the entries (ip-hostname)
# to be added to /etc/hosts
ETC_HOSTS_FILE = './etc-hosts'

# Define whether to add Mininet nodes to /etc/hosts file or not
ADD_ETC_HOSTS = True

# Define whether to start the node managers on the routers or not
START_NODE_MANAGERS = False

# Load environment variables from .env file
load_dotenv()

# Get node manager path
NODE_MANAGER_PATH = os.getenv('NODE_MANAGER_PATH', None)
if NODE_MANAGER_PATH is not None:
    NODE_MANAGER_PATH = os.path.join(NODE_MANAGER_PATH,
                                     'srv6_manager.py')
# Get gRPC server port
NODE_MANAGER_GRPC_PORT = os.getenv('NODE_MANAGER_GRPC_PORT', None)


class BaseNode(Host):

    def __init__(self, name, *args, **kwargs):
        dirs = [PRIVDIR]
        Host.__init__(self, name, privateDirs=dirs, *args, **kwargs)
        self.dir = "/tmp/%s" % name
        self.nets = []
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def config(self, **kwargs):
        # pylint: disable=arguments-differ

        # Init steps
        Host.config(self, **kwargs)
        # Iterate over the interfaces
        # first = True
        for intf in self.intfs.values():
            # Remove any configured address
            self.cmd('ifconfig %s 0' % intf.name)
            # # For the first one, let's configure the mgmt address
            # if first:
            #   first = False
            #   self.cmd('ip a a %s dev %s' %(kwargs['mgmtip'], intf.name))
        # let's write the hostname in /var/mininet/hostname
        self.cmd("echo '" + self.name + "' > " + PRIVDIR + "/hostname")
        if os.path.isfile(BASEDIR + self.name + "/start.sh"):
            self.cmd('source %s' % BASEDIR + self.name + "/start.sh")

    def cleanup(self):
        def remove_if_exists(filename):
            if os.path.exists(filename):
                os.remove(filename)

        Host.cleanup(self)
        # Rm dir
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)

        remove_if_exists(BASEDIR + self.name + "/zebra.pid")
        remove_if_exists(BASEDIR + self.name + "/zebra.log")
        remove_if_exists(BASEDIR + self.name + "/zebra.sock")
        remove_if_exists(BASEDIR + self.name + "/isis8d.pid")
        remove_if_exists(BASEDIR + self.name + "/isis8d.log")
        remove_if_exists(BASEDIR + self.name + "/isisd.log")
        remove_if_exists(BASEDIR + self.name + "/isisd.pid")

        remove_if_exists(OUTPUT_PID_TABLE_FILE)

        # if os.path.exists(BASEDIR+self.name+"/zebra.pid"):
        #     os.remove(BASEDIR+self.name+"/zebra.pid")

        # if os.path.exists(BASEDIR+self.name+"/zebra.log"):
        #     os.remove(BASEDIR+self.name+"/zebra.log")

        # if os.path.exists(BASEDIR+self.name+"/zebra.sock"):
        #     os.remove(BASEDIR+self.name+"/zebra.sock")

        # if os.path.exists(BASEDIR+self.name+"/ospfd.pid"):
        #     os.remove(BASEDIR+self.name+"/ospfd.pid")

        # if os.path.exists(BASEDIR+self.name+"/ospfd.log"):
        #     os.remove(BASEDIR+self.name+"/ospfd.log")

        # if os.path.exists(OUTPUT_PID_TABLE_FILE):
        #     os.remove(OUTPUT_PID_TABLE_FILE)


class Router(BaseNode):
    def __init__(self, name, *args, **kwargs):
        BaseNode.__init__(self, name, *args, **kwargs)

    def config(self, **kwargs):
        # Init steps
        BaseNode.config(self, **kwargs)
        # Start node managers
        if START_NODE_MANAGERS:
            self.cmd('python %s --grpc-port %s &'
                     % (NODE_MANAGER_PATH, NODE_MANAGER_GRPC_PORT))


# the add_link function creates a link and assigns the interface names
# as node1-node2 and node2-node1
def add_link(my_net, node1, node2, delay_val=None):
    # Cria o link normal
    link = my_net.addLink(node1, node2,
                          intfName1=node1.name + '-' + node2.name,
                          intfName2=node2.name + '-' + node1.name)

    if delay_val:
        link.custom_delay = delay_val

def create_topo(my_net):
    # pylint: disable=invalid-name, too-many-locals, too-many-statements

    h1 = my_net.addHost(name='h1', cls=BaseNode)
    h2 = my_net.addHost(name='h2', cls=BaseNode)


    controller = my_net.addHost(
        name='controller', cls=BaseNode, inNamespace=False)

    r1 = my_net.addHost(name='r1', cls=Router)
    r2 = my_net.addHost(name='r2', cls=Router)
    r3 = my_net.addHost(name='r3', cls=Router)
    r4 = my_net.addHost(name='r4', cls=Router)

    # note that if the interface names are not provided,
    # the order of adding link will determine the
    # naming of the interfaces (e.g. on r1: r1-eth0, r1-eth1, r1-eth2...)
    # it is possible to provide names as follows
    # Link(h1, r1, intfName1='h1-eth0', intfName2='r1-eth0')
    # the add_link function creates a link and assigns the interface names
    # as node1-node2 and node2-node1

    add_link(my_net, h1, r1)
    add_link(my_net, r1, r2)
    add_link(my_net, r2, r4, '20ms')
    add_link(my_net, r1, r3)
    add_link(my_net, r3, r4)
    add_link(my_net, h2, r4)

    # controller
    add_link(my_net, controller, r1)


def add_nodes_to_etc_hosts():
    # Get /etc/hosts
    etc_hosts = python_hosts.hosts.Hosts()
    # Import host-ip mapping defined in etc-hosts file
    count = etc_hosts.import_file(ETC_HOSTS_FILE)
    # Print results
    count = count['add_result']['ipv6_count'] + \
        count['add_result']['ipv4_count']
    print('*** Added %s entries to /etc/hosts\n' % count)


def remove_nodes_from_etc_hosts(net):
    print('*** Removing entries from /etc/hosts\n')
    # Get /etc/hosts
    etc_hosts = python_hosts.hosts.Hosts()
    for host in net.hosts:
        # Remove all the nodes from /etc/hosts
        etc_hosts.remove_all_matching(name=str(host))
    # Write changes to /etc/hosts
    etc_hosts.write()


def stop_all():
    # Clean Mininet emulation environment
    os.system('sudo mn -c')
    # Kill all the started daemons
    os.system('sudo killall sshd zebra isisd')


def extract_host_pid(dumpline):
    temp = dumpline[dumpline.find('pid=') + 4:]
    return int(temp[:len(temp) - 2])


def simple_test():
    "Create and test a simple network"

    # topo = RoutersTopo()
    # net = Mininet(topo=topo, build=False, controller=None)
    net = Mininet(topo=None, build=False, controller=None)
    create_topo(net)

    net.build()
    net.start()

    for link in net.links:
        if hasattr(link, 'custom_delay'):
            delay = link.custom_delay
            intf1_name = link.intf1.name
            intf2_name = link.intf2.name
            node1 = link.intf1.node
            node2 = link.intf2.node
                
            # Executa o comando direto no shell do roteador 1 e 2
            node1.cmd('tc qdisc add dev %s root netem delay %s' % (intf1_name, delay))
            node2.cmd('tc qdisc add dev %s root netem delay %s' % (intf2_name, delay))

    print("Dumping host connections")
    dumpNodeConnections(net.hosts)
    # print "Testing network connectivity"
    # net.pingAll()

    with open(OUTPUT_PID_TABLE_FILE, "w") as file:
        for host in net.hosts:
            file.write("%s %d\n" % (host, extract_host_pid(repr(host))))

    # Add Mininet nodes to /etc/hosts
    if ADD_ETC_HOSTS:
        add_nodes_to_etc_hosts()

    CLI(net)

    # Remove Mininet nodes from /etc/hosts
    if ADD_ETC_HOSTS:
        remove_nodes_from_etc_hosts(net)

    net.stop()
    stop_all()


def parse_arguments():
    # Get parser
    parser = ArgumentParser(
        description='Emulation of a Mininet topology (8 routers running '
                    'IS-IS, 1 controller in-band'
    )
    parser.add_argument(
        '--start-node-managers', dest='start_node_managers',
        action='store_true', default=False,
        help='Define whether to start node manager on routers or not'
    )
    parser.add_argument(
        '--no-etc-hosts', dest='add_etc_hosts',
        action='store_false', default=True,
        help='Define whether to add Mininet nodes to /etc/hosts file or not'
    )
    # Parse input parameters
    args = parser.parse_args()
    # Return the arguments
    return args


def __main():
    global ADD_ETC_HOSTS  # pylint: disable=global-statement
    global START_NODE_MANAGERS  # pylint: disable=global-statement
    global NODE_MANAGER_GRPC_PORT  # pylint: disable=global-statement
    # Parse command-line arguments
    args = parse_arguments()
    # Define whether to start node manager on routers or not
    START_NODE_MANAGERS = args.start_node_managers
    if START_NODE_MANAGERS:
        if NODE_MANAGER_PATH is None:
            print('Error: --start-node-managers requires NODE_MANAGER_PATH '
                  'variable')
            print('NODE_MANAGER_PATH variable not set in .env file\n')
            sys.exit(-2)
        if not os.path.exists(NODE_MANAGER_PATH):
            print('Error: --start-node-managers requires NODE_MANAGER_PATH '
                  'variable')
            print('NODE_MANAGER_PATH defined in .env file '
                  'points to a non existing folder\n')
            sys.exit(-2)
        if NODE_MANAGER_GRPC_PORT is None:
            print('Error: --start-node-managers requires '
                  'NODE_MANAGER_GRPC_PORT variable')
            print('NODE_MANAGER_GRPC_PORT variable not set in .env file\n')
            sys.exit(-2)
    # Define whether to add Mininet nodes to /etc/hosts file or not
    ADD_ETC_HOSTS = args.add_etc_hosts
    # Tell mininet to print useful information
    setLogLevel('info')
    simple_test()


if __name__ == '__main__':
    __main()
