# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import octoprint.plugin

from flask import make_response
from threading import Timer
from octoprint.events import Events

_TIME_REMAINING_FORMAT = "{hours:d}h {minutes:d}min"
_TIME_DAYS_REMAINING_FORMAT = "{days:d}d {hours:d}h {minutes:d}min"
_SECONDS_PER_DAY = 86400
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60

def is_string(val):
	return isinstance(val, ("".__class__, u"".__class__))

# From OctoPrint/OctoPrint-Pushbullet
def _get_time_from_seconds(seconds, default=None):
	if seconds is None:
		return default

	try:
		seconds = int(seconds)
	except ValueError:
		return default

	days, seconds = divmod(seconds, _SECONDS_PER_DAY)
	hours, seconds = divmod(seconds, _SECONDS_PER_HOUR)
	minutes, seconds = divmod(seconds, _SECONDS_PER_MINUTE)

	if days > 0:
		return _TIME_DAYS_REMAINING_FORMAT.format(**locals())
	else:
		return _TIME_REMAINING_FORMAT.format(**locals())

class EndScriptsPlugin(octoprint.plugin.TemplatePlugin,
											 octoprint.plugin.AssetPlugin,
											 octoprint.plugin.SettingsPlugin,
											 octoprint.plugin.SimpleApiPlugin,
											 octoprint.plugin.EventHandlerPlugin,
											 octoprint.plugin.ReloadNeedingPlugin):

	def __init__(self):
		self.scripts = []
		self._queue = []

		self._printData = None
		self._state = None

	def initialize(self):
		self.scripts = self._parse_scripts(self._settings.get(["scripts"]), True)

		self._printData = None
		self._state = self._printer.get_state_id()

	def _parse_scripts(self, scripts, reset = False):
		result = []

		if not isinstance(scripts, list):
			self._logger.warning("Invalid scripts: %s", scripts)
			return result

		for script in scripts:
			if not isinstance(script, dict):
				self._logger.warning("Invalid script")
				continue

			if (not "name" in script or not is_string(script["name"])):
				self._logger.warning("Invalid script: bad 'name' key")
				continue

			script["name"] = script["name"].strip()

			if not len(script["name"]):
				self._logger.warning("Invalid script: bad 'name' key")
				continue

			if (not "commands" in script or
			    not isinstance(script["commands"], list)):
				self._logger.warning("Invalid script: bad 'commands' key")
				continue

			commands = []

			for command in script["commands"]:
				if is_string(command):
					commands.append(command.strip())

			if not len(commands):
				self._logger.warning("Invalid script: no command provided")
				continue

			if ("delay" in script and
			    (not isinstance(script["delay"], int) or
			     script["delay"] < 0 or
			     script["delay"] > 86400)):
				self._logger.warning("Invalid script: bad 'delay' key")
				continue

			result.append(dict(
				name = script["name"],
				commands = commands,
				delay = script.get("delay", 0),
				auto_reset = script.get("auto_reset", False),
				enabled = (script.get("enabled", False) and
									 (not reset or not script.get("auto_reset", False)))
			))

		self._logger.debug("Scripts: %s", result)

		return result

	def _queue_cleanup(self):
		for index in reversed(range(len(self._queue))):
			if (not isinstance(self._queue[index], Timer) or
			    not self._queue[index].is_alive()):
				del self._queue[index]

	def _queue_cancel(self):
		for index in reversed(range(len(self._queue))):
			if (isinstance(self._queue[index], Timer) and
			    self._queue[index].is_alive()):
				self._logger.debug("Cancel script: %s", self._queue[index].name)

				self._plugin_manager.send_plugin_message(self._identifier, dict(
					notification_warning = ("Cancel script: {0:s}".format(self._queue[index].name))
				))

				self._queue[index].cancel()

			del self._queue[index]

	def _format_commands(self, commands, data):
		placeholders = dict(
			file = data.get("name"),
			elapsed_time = _get_time_from_seconds(data.get("time"), "?")
		)

		result = []

		for index in range(len(commands)):
			command = commands[index].format(**placeholders).strip()

			if len(command):
				result.append(command)

		return result

	def _queue_script(self, delay, name, commands):
		self._logger.debug("Queuing script: %s", name)

		self._plugin_manager.send_plugin_message(self._identifier, dict(
			notification_success = ("Queuing script: {0:s}".format(name))
		))

		thread = Timer(delay, self._run_script, [ name, commands ])
		thread.name = name
		thread.start()

		self._queue.append(thread)

	def _run_script(self, name, commands):
		self._logger.debug("Running script: %s", name)

		self._plugin_manager.send_plugin_message(self._identifier, dict(
			notification_success = ("Running script: {0:s}".format(name))
		))

		self._printer.commands(commands)

	def _run_end_scripts(self, data):
		for index in range(len(self.scripts)):
			if not self.scripts[index]["enabled"]:
				self._logger.debug("Script disabled: %s", self.scripts[index]["name"])
				continue

			try:
				formatted = self._format_commands(self.scripts[index]["commands"], data)
			except KeyError as err:
				self._logger.error("Invalid script G-code: %s", self.scripts[index]["name"])

				self._plugin_manager.send_plugin_message(self._identifier, dict(
					notification_error = ("Invalid script G-code: {0:s}".format(self.scripts[index]["name"]))
				))

				if self.scripts[index]["auto_reset"]:
					self.scripts[index]["enabled"] = False

				continue

			if self.scripts[index]["delay"] > 0:
				self._queue_script(self.scripts[index]["delay"], self.scripts[index]["name"], formatted)
			else:
				self._run_script(self.scripts[index]["name"], formatted)

			if self.scripts[index]["auto_reset"]:
				self.scripts[index]["enabled"] = False

		self._settings.set(["scripts"], self.scripts)
		self._settings.save()

		self._plugin_manager.send_plugin_message(self._identifier, dict(
			scripts = self.scripts
		))

	#~~ TemplatePlugin

	def get_template_configs(self):
		return [
			dict(
				type = "sidebar",
				name = "End Scripts",
				custom_bindings = True,
				icon = "tasks",
				template_header = "endscripts_sidebar_header.jinja2",
				data_bind = "visible: scripts().length > 0"
			),
			dict(
				type = "settings",
				custom_bindings = True
			)
		]

	#~~ AssetPlugin

	def get_assets(self):
		return dict(
			js = [
				"js/endscripts.js"
			],
			css = [
				"css/endscripts.css"
			]
		)

	#~~ SettingsPlugin

	def get_settings_defaults(self):
		return dict(
			scripts = []
		)

	def on_settings_save(self, data):
		if "scripts" in data:
			self.scripts = self._parse_scripts(data["scripts"])
			data["scripts"] = self.scripts

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		self._plugin_manager.send_plugin_message(self._identifier, dict(
			scripts = self.scripts
		))

	#~~ SimpleApiPlugin

	def get_api_commands(self):
		return dict(
			cancel_queue = [],
			enable = ["index"],
			disable = ["index"]
		)

	def on_api_command(self, command, data):
		if command == "cancel_queue":
			self._queue_cancel()
			return
		elif command == "enable":
			if (not isinstance(data["index"], int) or
			    data["index"] not in range(len(self.scripts))):
				return make_response("Bad Request", 400)

			self.scripts[data["index"]]["enabled"] = True
		elif command == "disable":
			if (not isinstance(data["index"], int) or
			    data["index"] not in range(len(self.scripts))):
				return make_response("Bad Request", 400)

			self.scripts[data["index"]]["enabled"] = False
		else:
			return make_response("Not Found", 404)

		self._settings.set(["scripts"], self.scripts)
		self._settings.save()

		self._plugin_manager.send_plugin_message(self._identifier, dict(
			scripts = self.scripts
		))

	def on_api_get(self, request):
		return make_response("Not Found", 404)

	#~~ EventHandlerPlugin

	def on_event(self, event, payload):
		if event == Events.PRINTER_STATE_CHANGED:
			self._queue_cleanup()

			if (self._printData is not None and
			    self._state == "FINISHING" and
			    payload["state_id"] == "OPERATIONAL"):
				self._run_end_scripts(self._printData)

				self._printData = None
		elif event == Events.PRINT_DONE:
			if self._printer.get_state_id() == "OPERATIONAL":
				self._run_end_scripts(payload)

				self._printData = None
			else:
				self._printData = payload
		elif event in [Events.PRINT_STARTED, Events.PRINT_CANCELLING, Events.PRINT_CANCELLED, Events.PRINT_FAILED]:
			self._printData = None
		elif event == Events.USER_LOGGED_IN:
			self._plugin_manager.send_plugin_message(self._identifier, dict(
				scripts = self.scripts
			))
		elif event in [Events.SHUTDOWN, Events.DISCONNECTED]:
			for index in reversed(range(len(self._queue))):
				if (isinstance(self._queue[index], Timer) and
						self._queue[index].is_alive()):
					self._queue[index].cancel()

				del self._queue[index]

			return


		self._state = self._printer.get_state_id()

	def get_update_information(self):
		return dict(
			endscripts = dict(
				displayName = self._plugin_name,
				displayVersion = self._plugin_version,
				type = "github_release",
				user = "Desuuuu",
				repo = "OctoPrint-EndScripts",
				current = self._plugin_version,
				pip = "https://github.com/Desuuuu/OctoPrint-EndScripts/archive/{target_version}.zip"
			)
		)

__plugin_name__ = "End Scripts"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
	plugin = EndScriptsPlugin()

	global __plugin_implementation__
	__plugin_implementation__ = plugin

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": plugin.get_update_information
	}
