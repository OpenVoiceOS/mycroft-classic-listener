# Copyright 2017 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from ovos_bus_client.client import MessageBusClient
from ovos_utils import wait_for_exit_signal

from mycroft_classic_listener.service import ClassicListener, on_error, on_stopping, on_ready


def main(ready_hook=on_ready, error_hook=on_error, stopping_hook=on_stopping,
         watchdog=lambda: None):
    global bus
    global loop
    global config
    try:
        bus = MessageBusClient()
        bus.run_in_thread()
        service = ClassicListener(bus, ready_hook,
                                  error_hook,
                                  stopping_hook,
                                  watchdog)
        service.daemon = True
        service.start()

    except Exception as e:
        error_hook(e)
    else:
        wait_for_exit_signal()
        bus.close()


if __name__ == "__main__":
    main()
