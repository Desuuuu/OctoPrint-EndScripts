$(function() {
  function EndScriptsViewModel() {
    var self = this;

    self.scripts = ko.observableArray();

    self.cancelQueue = function() {
      $.ajax({
        url: API_BASEURL + 'plugin/endscripts',
        type: 'POST',
        dataType: 'json',
        data: JSON.stringify({
          command: 'cancel_queue'
        }),
        contentType: 'application/json; charset=UTF-8'
      });
    };

    self.toggleScript = function(index) {
      $.ajax({
        url: API_BASEURL + 'plugin/endscripts',
        type: 'POST',
        dataType: 'json',
        data: JSON.stringify({
          command: this.enabled ? 'enable' : 'disable',
          index: index
        }),
        contentType: 'application/json; charset=UTF-8'
      });
    };

    self.onDataUpdaterPluginMessage = function(plugin, data) {
      if (plugin !== 'endscripts' || typeof data !== 'object' || !data) {
        return;
      }

      if (data.hasOwnProperty('scripts')) {
        self.scripts(data.scripts);
      }

      if (data.hasOwnProperty('notification_success')) {
        new PNotify({
          title: 'End Scripts',
          text: data.notification_success.trim(),
          type: 'success'
        });
      }

      if (data.hasOwnProperty('notification_warning')) {
        new PNotify({
          title: 'End Scripts',
          text: data.notification_warning.trim(),
          type: 'warning'
        });
      }

      if (data.hasOwnProperty('notification_error')) {
        new PNotify({
          title: 'End Scripts',
          text: data.notification_error.trim(),
          type: 'error'
        });
      }
    };
  }

  function EndScriptsSettingsViewModel(parameters) {
    var self = this;

    var editorModal = $('#octoprint_endscripts_scripteditor');

    self.globalScripts = null;
    self.scripts = ko.observableArray();

    self.selectedScript = {
      index: ko.observable(-1),
      name: ko.observable(''),
      commands: ko.observable(''),
      delay: ko.observable(0),
      auto_reset: ko.observable(false)
    };

    self.selectedScript.name.hasFocus = ko.observable(false);
    self.selectedScript.name.hasError = ko.observable(false);
    self.selectedScript.name.hasFocus.subscribe(function(hasFocus) {
      if (hasFocus) {
        this.hasError(false);
      }
    }, self.selectedScript.name);

    self.selectedScript.commands.hasFocus = ko.observable(false);
    self.selectedScript.commands.hasError = ko.observable(false);
    self.selectedScript.commands.hasFocus.subscribe(function(hasFocus) {
      if (hasFocus) {
        this.hasError(false);
      }
    }, self.selectedScript.commands);

    self.selectedScript.delay.hasFocus = ko.observable(false);
    self.selectedScript.delay.hasError = ko.observable(false);
    self.selectedScript.delay.hasFocus.subscribe(function(hasFocus) {
      if (hasFocus) {
        this.hasError(false);
      }
    }, self.selectedScript.delay);

    self.onBeforeBinding = function() {
      self.settings = parameters[0].settings;
    };

    self.onSettingsShown = function() {
      self.scripts($.extend(true, [], self.globalScripts));
    };

    self.onSettingsBeforeSave = function() {
      self.settings.plugins.endscripts.scripts(ko.mapping.toJS(self.scripts));
    }

    self.moveScriptUp = function(index) {
      if (index < 1) {
        return;
      }

      self.scripts.splice(index, 1);
      self.scripts.splice(index - 1, 0, this);
    };

    self.moveScriptDown = function(index) {
      if (index >= self.scripts().length - 1) {
        return;
      }

      self.scripts.splice(index, 1);
      self.scripts.splice(index + 1, 0, this);
    };

    self.editScript = function(index) {
      self.selectedScript.index(index);
      self.selectedScript.name(this.name);
      self.selectedScript.commands(this.commands.join('\n'));
      self.selectedScript.delay(this.delay);
      self.selectedScript.auto_reset(this.auto_reset);

      self.selectedScript.name.hasError(false);
      self.selectedScript.commands.hasError(false);
      self.selectedScript.delay.hasError(false);

      editorModal.modal('show');
    };

    self.addScript = function() {
      self.selectedScript.index(-1);
      self.selectedScript.name('');
      self.selectedScript.commands('');
      self.selectedScript.delay(0);
      self.selectedScript.auto_reset(false);

      self.selectedScript.name.hasError(false);
      self.selectedScript.commands.hasError(false);
      self.selectedScript.delay.hasError(false);

      editorModal.modal('show');
    };

    self.saveScript = function() {
      var hasErrors = false;

      var script = ko.mapping.toJS(self.selectedScript);

      script.name = script.name.trim();
      script.commands = script.commands.trim();
      script.delay = parseInt(script.delay, 10);

      if (script.name.length < 1 || script.name.length > 32) {
        hasErrors = true;
        self.selectedScript.name.hasError(true);
      }

      if (script.commands.length < 1) {
        hasErrors = true;
        self.selectedScript.commands.hasError(true);
      }

      if (isNaN(script.delay) || script.delay < 0 || script.delay > 86400) {
        hasErrors = true;
        self.selectedScript.delay.hasError(true);
      }

      if (hasErrors) {
        self.selectedScript.name(script.name);
        self.selectedScript.commands(script.commands);

        if (editorModal.hasClass('shake')) {
          editorModal.removeClass('shake');
        }

        setTimeout(function() {
          editorModal.addClass('animated shake');
        }, 0);
        return;
      }

      if (script.index < 0) {
        self.scripts.push({
          name: script.name,
          commands: script.commands.split('\n').map(function(command) {
            return command.trim();
          }),
          delay: script.delay,
          auto_reset: !!script.auto_reset,
          enabled: false
        });
      } else if (script.index <= self.scripts().length - 1) {
        var enabled = self.scripts()[script.index].enabled;

        self.scripts.splice(script.index, 1);
        self.scripts.splice(script.index, 0, {
          name: script.name,
          commands: script.commands.split('\n').map(function(command) {
            return command.trim();
          }),
          delay: script.delay,
          auto_reset: !!script.auto_reset,
          enabled: !!enabled
        });
      }

      editorModal.modal('hide');
    };

    self.removeScript = function(index) {
      self.scripts.splice(index, 1);
    };

    self.onDataUpdaterPluginMessage = function(plugin, data) {
      if (plugin !== 'endscripts' || typeof data !== 'object' || !data) {
        return;
      }

      if (data.hasOwnProperty('scripts')) {
        self.globalScripts = data.scripts;

        self.scripts($.extend(true, [], self.globalScripts));
      }
    };
  }

  OCTOPRINT_VIEWMODELS.push({
    construct: EndScriptsViewModel,
    elements: ['#sidebar_plugin_endscripts_wrapper']
  }, {
    construct: EndScriptsSettingsViewModel,
    dependencies: ['settingsViewModel'],
    elements: ['#settings_plugin_endscripts']
  });
});
