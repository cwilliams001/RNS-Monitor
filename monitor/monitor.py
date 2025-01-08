import RNS
import time
import json
import asyncio
from aiohttp import web
from datetime import datetime, timedelta

class ReticulumMonitor:
    def __init__(self):
        self.reticulum = RNS.Reticulum(require_shared_instance=True)
        self.status_history = {}
        self.last_check = None

    def get_interface_status(self):
        try:
            stats = self.reticulum.get_interface_stats()
            if stats is None:
                return None

            current_time = datetime.now().isoformat()
            status_data = {
                'timestamp': current_time,
                'interfaces': []
            }

            for ifstat in stats['interfaces']:
                interface_status = {
                    'name': ifstat['name'],
                    'status': 'up' if ifstat['status'] else 'down',
                    'mode': self._get_mode_string(ifstat['mode']),
                    'bitrate': ifstat.get('bitrate'),
                    'traffic': {
                        'rx': ifstat['rxb'],
                        'tx': ifstat['txb']
                    }
                }

                # Add additional metrics if available
                if 'peers' in ifstat:
                    interface_status['peers'] = ifstat['peers']
                if 'clients' in ifstat:
                    interface_status['clients'] = ifstat['clients']
                if 'incoming_announce_frequency' in ifstat:
                    interface_status['announces'] = {
                        'incoming': ifstat['incoming_announce_frequency'],
                        'outgoing': ifstat['outgoing_announce_frequency']
                    }

                status_data['interfaces'].append(interface_status)

                # Store in history
                if ifstat['name'] not in self.status_history:
                    self.status_history[ifstat['name']] = []
                self.status_history[ifstat['name']].append({
                    'timestamp': current_time,
                    'status': interface_status['status']
                })
                # Keep only last 24 hours of history
                cutoff_time = datetime.fromisoformat(current_time) - timedelta(hours=24)
                self.status_history[ifstat['name']] = [
                    entry for entry in self.status_history[ifstat['name']]
                    if datetime.fromisoformat(entry['timestamp']) > cutoff_time
                ]

            self.last_check = current_time
            return status_data

        except Exception as e:
            print(f"Error getting interface status: {str(e)}")
            return None

    def _get_mode_string(self, mode):
        mode_map = {
            RNS.Interfaces.Interface.Interface.MODE_ACCESS_POINT: "Access Point",
            RNS.Interfaces.Interface.Interface.MODE_POINT_TO_POINT: "Point-to-Point",
            RNS.Interfaces.Interface.Interface.MODE_ROAMING: "Roaming",
            RNS.Interfaces.Interface.Interface.MODE_BOUNDARY: "Boundary",
            RNS.Interfaces.Interface.Interface.MODE_GATEWAY: "Gateway"
        }
        return mode_map.get(mode, "Full")

class WebServer:
    def __init__(self, monitor):
        self.monitor = monitor
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        self.app.router.add_get('/', self.handle_root)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_static('/static', 'static')

    async def handle_root(self, request):
        return web.FileResponse('static/index.html')

    async def handle_status(self, request):
        status = self.monitor.get_interface_status()
        if status is None:
            return web.json_response({'error': 'Failed to get status'}, status=500)
        return web.json_response(status)

async def periodic_status_check(monitor):
    while True:
        monitor.get_interface_status()
        await asyncio.sleep(60)

async def main():
    # Initialize monitor
    monitor = ReticulumMonitor()

    # Start web server
    server = WebServer(monitor)
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    # Start periodic status checking
    asyncio.create_task(periodic_status_check(monitor))

    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
