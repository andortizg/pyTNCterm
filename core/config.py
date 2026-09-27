import json
import os
import copy

from core.paths import resource_path

# Built-in defaults, used if resources/default_config.json cannot be found
BUILTIN_DEFAULTS = {   'station': {'callsign': '', 'grid_locator': '', 'name': ''},
    'serial': {   'port': '',
                  'baudrate': 9600,
                  'databits': 8,
                  'stopbits': 1,
                  'parity': 'None',
                  'flow_control': 'None',
                  'send_mode': 'line',
                  'line_ending': 'CR'},
    'appearance': {   'font_family': 'Consolas',
                      'font_size': 11,
                      'monitor': {   'bg_color': '#0a1929',
                                     'text_color': '#4fc3f7',
                                     'info_color': '#ffd54f',
                                     'error_color': '#ef5350'},
                      'channel': {   'bg_color': '#0d1b2a',
                                     'rx_color': '#e0e0e0',
                                     'tx_color': '#00e676',
                                     'system_color': '#ffd54f'},
                      'input': {   'bg_color': '#1a1a2e',
                                   'text_color': '#00e676',
                                   'prompt_color': '#4fc3f7'},
                      'statusbar': {'bg_color': '#1b2838', 'text_color': '#b0bec5'}},
    'paths': {'yapp_download': '', 'yapp_upload': '', 'log_directory': ''},
    'window': {'width': 900, 'height': 700, 'x': -1, 'y': -1},
    'tnc': {   'model': 'Generic / TNC-2 Compatible',
               'autocomplete': True,
               'auto_init': True,
               'handshake': True},
    'yapp': {   'transparent': True,
                'trans_cmd': 'TRANS',
                'return_cmd': 'K',
                'block_delay_ms': 0}}


class Config:
    """
    Manages application configuration: loading, saving, and providing
    access to settings values.
    
    Config is stored as a nested dict and persisted to a JSON file.
    """

    USER_CONFIG_FILENAME = "pytncterm_config.json"

    def __init__(self):
        # _data: dict - the full configuration dictionary
        self._data = {}
        # _user_config_path: str - path to the user's config file
        self._user_config_path = self._get_user_config_path()
        self._load()

    def _get_user_config_path(self):
        """
        Returns the path for the user config file.
        Returns: str - full path to user config JSON
        """
        config_dir = os.path.join(os.path.expanduser("~"), ".pytncterm")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, self.USER_CONFIG_FILENAME)

    def _load(self):
        """
        Loads configuration: first defaults, then overrides with user config if it exists.
        """
        self._data = copy.deepcopy(BUILTIN_DEFAULTS)
        default_path = resource_path("default_config.json")
        if default_path and os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    self._deep_merge(self._data, json.load(f))
            except (json.JSONDecodeError, IOError):
                pass

        if os.path.exists(self._user_config_path):
            try:
                with open(self._user_config_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                self._deep_merge(self._data, user_data)
            except (json.JSONDecodeError, IOError):
                pass

    def _deep_merge(self, base, override):
        """
        Recursively merges override dict into base dict.
        
        Args:
            base: dict - the base dictionary (modified in place)
            override: dict - values to merge in
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def save(self):
        """
        Persists current configuration to the user config file.
        """
        tmp_path = self._user_config_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4)
        os.replace(tmp_path, self._user_config_path)

    def get(self, *keys, default=None):
        """
        Retrieves a nested config value using a sequence of keys.
        
        Args:
            *keys: str - sequence of keys to traverse (e.g., "serial", "baudrate")
            default: any - value to return if key path not found
        
        Returns: the value at the key path, or default
        """
        node = self._data
        for key in keys:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                return default
        return node

    def set(self, *args):
        """
        Sets a nested config value. Last argument is the value, preceding args are keys.
        
        Args:
            *args: sequence of keys followed by the value to set
                   e.g., set("serial", "baudrate", 9600)
        """
        if len(args) < 2:
            return
        keys = args[:-1]
        value = args[-1]
        node = self._data
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value

    def get_all(self):
        """
        Returns: dict - a deep copy of the full configuration
        """
        return copy.deepcopy(self._data)
