import aiohttp
from aiosseclient import aiosseclient
import asyncio
import json
import sys
import urllib
import argparse


def plain_port(port):
    if port.startswith('E'):
        return port[1:]
    return port


def push_gauge(buf, name, params, value):
    keys = ','.join(f'{k}="{v}"' for (k, v) in params.items())
    buf.append(f'{name}{{{keys}}} {value}')


def extract_data(ds, hostname):
    buf = []

    try:
        for module in ('czechlight-bidi-amp:narrow-1572', 'czechlight-bidi-amp:c-band'):
            module_data = ds[module]
            push_gauge(buf, 'edfa_pump_current', {'host': hostname, 'module': module}, module_data['pump'])
            for direction in ('east-to-west', 'west-to-east'):
                for point in ('input-power', 'output-power'):
                    push_gauge(buf, 'optical_power', {'host': hostname, 'module': module, 'direction': direction, 'where': point}, module_data[direction][point])
    except KeyError:
        pass

    try:
        MCs = ds['czechlight-roadm-device:media-channels']
        for channel in MCs:
            for point in ('common-in', 'common-out', 'leaf-in', 'leaf-out'):
                if point in channel['power']:
                    keys = {'host': hostname, 'channel': channel["channel"], 'where': point}
                    try:
                        if point == 'leaf-in':
                            keys['port'] = plain_port(channel['add']['port'])
                        elif point == 'leaf-out':
                            keys['port'] = plain_port(channel['drop']['port'])
                    except KeyError:
                        pass
                    push_gauge(buf, 'optical_power', keys, channel['power'][point])
    except KeyError:
        pass

    try:
        agg = ds['czechlight-roadm-device:aggregate-power']
        for point in ('common-in', 'common-out', 'express-in', 'express-out'):
            push_gauge(buf, 'optical_power', {'host': hostname, 'channel': '', 'where': point}, agg[point])
    except KeyError:
        pass

    try:
        agg = ds['czechlight-coherent-add-drop:aggregate-power']
        for point in ('drop', 'express-in', 'express-out'):
            push_gauge(buf, 'optical_power', {'host': hostname, 'channel': '', 'where': point}, agg[point])
        for port in ds['czechlight-coherent-add-drop:client-ports']:
            push_gauge(buf, 'optical_power', {'host': hostname, 'channel': '', 'where': port['port']}, port['input-power'])
    except KeyError:
        pass

    try:
        osc = ds['czechlight-roadm-device:line']['osc']
        for direction in ('rx', 'tx'):
            push_gauge(buf, 'optical_power', {'host': hostname, 'channel': 'OSC', 'where': f'LINE-{direction}'}, osc[f'{direction}-power'])
    except KeyError:
        pass

    return buf


def extract_spectrum(buf, ds, hostname):
    try:
        for point in ('common-in', 'common-out'):
            d = ds['czechlight-roadm-device:spectrum-scan'][point]
            lowest = d['lowest-frequency']
            step = d['step']
            for i, power in enumerate(d['p']):
                push_gauge(buf, 'spectrum_scan', {'host': hostname, 'freq': i * float(step) + float(lowest), 'where': point}, power)

    except KeyError:
        pass


async def read_via_restconf(hostname, queue):
    print(f'Handling {hostname}')
    url = urllib.parse.urlunparse(('http', hostname, '/telemetry/optics', None, None, None))
    while True:
        last_spectrum = None
        try:
            async for block in aiosseclient(url):
                ds = json.loads(block)['ietf-restconf:notification']['ietf-yang-push:push-update']['datastore-contents']
                buf = extract_data(ds, hostname)
                spectrum = ds.get('czechlight-roadm-device:spectrum-scan', None)
                if spectrum is not None and last_spectrum != ds['czechlight-roadm-device:spectrum-scan']:
                    extract_spectrum(buf, ds, hostname)
                    last_spectrum = ds['czechlight-roadm-device:spectrum-scan']
                if len(buf):
                    print(f'{hostname} -> {len(buf)}')
                    await queue.put('\n'.join(buf))

        except Exception as e:
            print(hostname, e)
            await asyncio.sleep(1)


async def push_to_tsdb(queue):
    timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=None, sock_read=None)
    while True:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while True:
                    entry = await queue.get()
                    async with session.post('http://localhost:8428/api/v1/import/prometheus', data=entry) as resp:
                        await resp.text()
        except aiohttp.client_exceptions.ClientError as e:
            print(e)
            await asyncio.sleep(1)


async def main(urls):
    queue = asyncio.Queue()
    await asyncio.gather(push_to_tsdb(queue), *(read_via_restconf(url, queue) for url in urls))


loop = asyncio.get_event_loop()
loop.run_until_complete(main(sys.argv[1:]))
