#!/usr/bin/env python

from subprocess import check_output

t = """Bus 001 Device 008: ID 239a:d1ed
Bus 001 Device 015: ID 045e:00db Microsoft Corp. Natural Ergonomic Keyboard 4000 V1.0
Bus 001 Device 014: ID 046d:c52f Logitech, Inc. Unifying Receiver
Bus 001 Device 013: ID 0b95:772a ASIX Electronics Corp. AX88772A Fast Ethernet
Bus 001 Device 012: ID 0d8c:0105 C-Media Electronics, Inc. CM108 Audio Controller
Bus 001 Device 011: ID 17e9:0117 DisplayLink 
Bus 001 Device 010: ID 1a40:0201 Terminus Technology Inc. FE 2.1 7-port Hub
Bus 001 Device 016: ID 04d9:1603 Holtek Semiconductor, Inc. Keyboard
Bus 001 Device 003: ID 0424:ec00 Standard Microsystems Corp. SMSC9512/9514 Fast Ethernet Adapter
Bus 001 Device 002: ID 0424:9514 Standard Microsystems Corp. 
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub"""

def parse_entry(line):
    location, description = line.split(':', 1)
    id_str, vid_pid_name = description.strip(' ').split(' ', 1)
    vid_pid = vid_pid_name.split(' ', 1)[0]
    vid, pid = map(lambda x: int(x, 16), vid_pid.split(':'))
    name = vid_pid_name.split(' ', 1)[1] if len(vid_pid_name.split(' ', 1)) > 1 else None
    strBus, bus, strDevice, device = location.split(' ', 3)
    bus = int(bus, 10)
    device = int(device, 10)
    return [bus, device, vid, pid, name]

def lsusb(output=None):
    lsusb_entries = []
    if not output:
        output = check_output(["lsusb"])
    if isinstance(output, bytes): output = output.decode("ascii")
    for line in [line.strip(' ') for line in output.split('\n') if line.strip(' ')]:
        entry = parse_entry(line)
        lsusb_entries.append(entry)
    return lsusb_entries

root_hub_keys = ["bus", "port", "dev", "class_s", "driver", "port_count", "speed",
    "sys_path", "dev_path", "devices"]
device_keys = ["port", "dev", "if_s", "class_s", "driver", "speed", "sys_path", "dev_path"]
entry_keys = ["vid", "pid", "name"]

def lsusb_tvv(output=None):
    root_hubs = []
    if not output:
        output = check_output(["lsusb", "-tvv"])
    if isinstance(output, bytes): output = output.decode("ascii")
    lines = list(filter(None, output.split('\n')))
    current_line = 0
    while True:
        line = lines[current_line].lstrip()
        desc_line = lines[current_line+1].lstrip()
        entry = parse_entry("Bus 000 Device 000: "+desc_line)[2:]
        path_line = lines[current_line+2].lstrip()
        #print(path_line.lstrip().split(' '))
        sys_path, dev_path = list(filter(None, path_line.lstrip().split(' ')))
        if line.startswith("/:"):
            # root hub line
            body = line.split(" ", 1)[1].lstrip()
            # bus number
            bus_s, body = body.split('.', 1)
            bus = int(bus_s.split(" ")[1], 10)
            # port number
            port_s, body = body.split(':', 1)
            port = int(port_s.split(" ")[1], 10)
            # dev number
            dev_s, body = body.lstrip(' ').split(', ', 1)
            dev = int(dev_s.split(" ")[1], 10)
            # class name
            class_s, body = body.lstrip(' ').split(', ', 1)
            clas = class_s.split("=")[1]
            # driver name and port number
            drv_s, speed_s = body.lstrip(' ').split(', ', 1)
            drv, portnum_s = drv_s.split("=")[1].split('/')
            portnum = int(portnum_s[:-1], 10)
            # speed
            speed = int(speed_s[:-1], 10)
            values = [bus, port, dev, clas, drv, portnum, speed]
            values += [sys_path, dev_path, []]
            root_hub = dict(zip(root_hub_keys, values))
            root_hub.update(dict(zip(entry_keys, entry)))
            root_hubs.append(root_hub)
        elif line.startswith("|__"):
            body = line.split(" ", 1)[1]
            #print(body)
            # port number
            _, ports, body = body.split(" ", 2)
            port = int(ports[:-1], 10)
            dev_s, if_s, class_s, drv_s, speed_s = body.lstrip().split(", ")
            # dev number
            dev = int(dev_s.split(" ")[1], 10)
            # if number
            ifn = int(if_s.split(" ")[1], 10)
            # class name
            clas = class_s.split("=")[1]
            # driver name
            #drv_s, speed_s = body.lstrip(' ').split(', ', 1)
            drv = drv_s.split("=")[1]
            # speed
            speed = int(speed_s[:-1], 10)
            values = [port, dev, ifn, clas, drv, speed, sys_path, dev_path]
            device = dict(zip(device_keys, values))
            device.update(dict(zip(entry_keys, entry)))
            root_hubs[-1]["devices"].append(device)
        current_line += 3
        if current_line == len(lines):
            break
    return root_hubs

def print_lsusb_tvv():
    for l in lsusb_tvv():
        #print(l)
        l["bus"] = str(l["bus"]).zfill(2)
        l["vid"] = hex(l["vid"])[2:].zfill(4)
        l["pid"] = hex(l["pid"])[2:].zfill(4)
        print("/:  Bus {bus}.Port {port}: Dev {dev}, Class={class_s}, Driver={driver}/{port_count}p, {speed}M".format(**l))
        print("    ID {vid}:{pid} {name}".format(**l))
        print("    {sys_path} {dev_path}".format(**l))
        for device in l["devices"]:
            device["vid"] = hex(device["vid"])[2:].zfill(4)
            device["pid"] = hex(device["pid"])[2:].zfill(4)
            #print(device)
            print("    |__ Port {port}: Dev {dev}, If {if_s}, Class={class_s}, Driver={driver}, {speed}M".format(**device))
            print("        ID {vid}:{pid} {name}".format(**device))
            print("        {sys_path} {dev_path}".format(**device))

if __name__ == "__main__":
    print(lsusb())
    #print(lsusb_tvv())
    print_lsusb_tvv()

