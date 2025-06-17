import unittest
import subprocess
#Description used for all interfaces
from copy import copy

if_description = {
   'state':'down',
   'addr':None,
   'mask':0,
   'addr6':None,
   'mask6':0,
   'ph_addr':None
}

td1 = '1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000\n    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n    inet 127.0.0.1/8 scope host lo\n       valid_lft forever preferred_lft forever\n    inet6 ::1/128 scope host \n       valid_lft forever preferred_lft forever\n2: wlp1s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000\n    link/ether ab:cd:ef:01:23:45 brd ff:ff:ff:ff:ff:ff\n    inet 192.168.1.2/24 brd 192.168.1.255 scope global dynamic noprefixroute wlp1s0\n       valid_lft 806560sec preferred_lft 806560sec\n    inet6 abcd:ef01:2345:0:abcd:ef01:2345:6789/64 scope global temporary dynamic \n       valid_lft 7078sec preferred_lft 3478sec\n3: virbr0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default qlen 1000\n    link/ether ab:cd:ef:01:23:46 brd ff:ff:ff:ff:ff:ff\n    inet 192.168.2.1/24 brd 192.168.2.255 scope global virbr0\n       valid_lft forever preferred_lft forever\n'

def parse_params(param_string):
    state = None
    words = param_string.split(" ")
    for index, word in enumerate(words):
        if word == 'state':
            state = words[index+1].lower()
    return {'state':state}

def parse_ip_addr(output=None):
    interfaces = {}
    current_if = None
    if output == None:
        output = subprocess.check_output(['ip', 'addr'])
    if isinstance(output, bytes): output = output.decode("ascii")
    output = [line for line in output.split('\n') if line != ""]
    for line in output:
        if line[0].isdigit(): #First line for interface
            num, if_name, params = line.split(':', 2)
            if_name = if_name.strip(" ")
            current_if = if_name
            interfaces[if_name] = copy(if_description)
            param_dict = parse_params(params)
            interfaces[if_name].update(param_dict)
        else: #Lines that continue describing interfaces
            line = line.lstrip()
            words = line.split(" ")
            if words[0] == "inet":
                ip = words[1]
                mask = 0
                if "/" in ip:
                    ip, mask = ip.rsplit('/', 1)
                interfaces[current_if]['addr'] = ip
                interfaces[current_if]['mask'] = mask
            elif words[0] == 'link/ether':
                interfaces[current_if]['ph_addr'] = words[1]
            elif words[0] == 'inet6':
                ip = words[1]
                mask = 0
                if "/" in ip:
                    ip, mask = ip.rsplit('/', 1)
                interfaces[current_if]['addr6'] = ip
                interfaces[current_if]['mask6'] = mask
    return interfaces

def get_network_from_ip(ip_str):
    ip, mask_len_str = ip_str.split('/')
    mask_len = int(mask_len_str)
    ip_byte_repr_str = ip_to_byte_str(ip)
    net_ip_byte_repr_str = ip_byte_repr_str[:mask_len][::-1].zfill(32)[::-1]
    network_ip = byte_str_to_ip(net_ip_byte_repr_str)
    return "{}/{}".format(network_ip, mask_len_str)

def ip_to_byte_str(ip):
    octets = ip.split('.')
    ip_byte_repr_str = "".join([bin(int(octet))[2:].zfill(8) for octet in octets])
    return ip_byte_repr_str

def byte_str_to_ip(byte_str):
    octets = [str(int(byte_str[i*8:][:8], 2)) for i in range(4)]
    ip = ".".join(octets)
    return ip

def sort_ips(ips):
    #Let's try and sort the IPs by their integer representation
    ip_to_int_repr = {}
    for ip in ips:
        #Converting IP to its integer value
        int_repr = int(ip_to_byte_str(ip), 2)
        #Adding it to a dictionary to preserve integer_ip-to-ip link
        ip_to_int_repr[int_repr] = ip
    #Sorting the integer representations
    int_reprs = ip_to_int_repr.keys()
    int_reprs.sort()
    #Now returning the IPs associated with integer representations - by order of elements the sorted list
    return [ip_to_int_repr[int_repr] for int_repr in int_reprs]

class TestIfInfo(unittest.TestCase):

    def test_parse_ip_addr(self):
        """ tests parse_ip_addr function """
        output = parse_ip_addr(output=td1)
        assert output == {'lo': {'state': 'unknown', 'addr': '127.0.0.1', 'mask': '8', 'addr6': '::1', 'mask6': '128', 'ph_addr': None}, 'wlp1s0': {'state': 'up', 'addr': '192.168.1.2', 'mask': '24', 'addr6': 'abcd:ef01:2345:0:abcd:ef01:2345:6789', 'mask6': '64', 'ph_addr': 'ab:cd:ef:01:23:45'}, 'virbr0': {'state': 'down', 'addr': '192.168.2.1', 'mask': '24', 'addr6': None, 'mask6': 0, 'ph_addr': 'ab:cd:ef:01:23:46'}}

    def test_get_network_from_ip(self):
        """ tests get_network_from_ip function """
        ip = "192.168.88.153/24"
        network = get_network_from_ip(ip)
        assert network == "192.168.88.0/24"

if __name__ == "__main__":
    unittest.main()
