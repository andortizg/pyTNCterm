import json
import os
import copy


class Config:
    """
    Manages application configuration: loading, saving, and providing
    access to settings values.
    
    Config is stored as a nested dict and persisted to a JSON file.
    """

    DEFAULT_CONFIG_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "resources", "default_config.json"
    )
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
        with open(self.DEFAULT_CONFIG_PATH, "r") as f:
            self._data = json.load(f)

        if os.path.exists(self._user_config_path):
            try:
                with open(self._user_config_path, "r") as f:
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
        with open(self._user_config_path, "w") as f:
            json.dump(self._data, f, indent=4)

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
