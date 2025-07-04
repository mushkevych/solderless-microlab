"""
Module defining API.
"""

import glob
import json
import os
from http import HTTPStatus
from os.path import join
from pathlib import Path

from flask import jsonify, request, send_file, Response
from pydantic_core import ValidationError
from werkzeug.utils import secure_filename

import recipes.core
from api.app import FlaskApp
from config import microlab_config as config
from localization import load_translation
from microlab.interface import MicrolabInterface
from recipes.model import MicrolabRecipe


class RouteManager:

    def __init__(self, flask_app: FlaskApp, microlab_interface: MicrolabInterface):
        self._flask_app = flask_app
        self._microlab_interface = microlab_interface
        self._register_routes()

    # /list
    def _list_recipes(self) -> Response:
        """
        List all available recipes

        :return:
        list
            a list containing the names of the recipes. ex: ['recipe1','recipe2']
        """
        recipe_names = list(map(lambda recipe: recipe.title, recipes.core.get_recipe_list()))
        return jsonify(recipe_names)

    # /recipe/<name>
    def _send_recipe(self, name: str) -> Response:
        recipe = recipes.core.get_recipe_by_name(name)
        return jsonify(recipe.model_dump())

    # /status
    def _status(self) -> Response:
        """
        Get the status of the app.

        :return:
        object
            message
                The message to be displayed to the user.
            options
                null or a list of strings to display to the user as selectable options.
            recipe
                Name of the currently running recipe or null if none is running.
            step
                The step number or -1 if no recipe is running
            time
                The number of seconds the current step will execute for
            icon
                String indicating an icon to display to the user or undefined
                if the recipe does not specify an icon for the step.
                One of:
                    reaction_complete
                    cooling
                    crystalisation
                    dispensing
                    dry
                    filter
                    heating
                    human_task
                    inspect
                    load_syringe
                    maintain_cool
                    maintain_heat
                    reaction_chamber
                    rinse
                    set_up_cooling
                    set_up_heating
                    stirring
                    temperature
            status
                The state of the application. One of:
                    idle
                        App is waiting for the user to start a recipe
                    running
                        App is running a recipe and doesn't need any input from the user
                    user_input
                        App is waiting for the user to make a decision. See options.
                    complete
                        Recipe is complete.
                    error
                        A system error has occurred.
        """
        return jsonify(self._microlab_interface.status())

    # /start/<name>
    def _start(self, name: str) -> tuple[Response, int]:
        """
        Start running a recipe.

        :param name:
            The recipe name. Must be one of the items returned by /list
        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        t = load_translation()
        recipe = recipes.core.get_recipe_by_name(name)
        if recipe is None:
            return jsonify({'response': 'error', 'message': t['recipe-not-found']}), HTTPStatus.NOT_FOUND

        (state, msg) = self._microlab_interface.start(name)
        if state:
            return jsonify({'response': 'ok'}), HTTPStatus.OK
        else:
            return jsonify({'response': 'error', 'message': msg}), HTTPStatus.INTERNAL_SERVER_ERROR

    # /stop
    def _stop(self) -> Response:
        """
        Stop the currently running recipe.

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        self._microlab_interface.stop()
        return jsonify({'response': 'ok'})

    # /select/option/<name>
    def _select_option(self, name: str) -> tuple[Response, int]:
        """
        Provide user selected input.

        :param name:
        The name of the user selected option. This must be one of the strings presented in the
        "options" list in the /status call.

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        (state, msg) = self._microlab_interface.select_option(name)
        if state:
            return jsonify({'response': 'ok'}), HTTPStatus.OK
        else:
            return jsonify({'response': 'error', 'message': msg}), HTTPStatus.BAD_REQUEST

    # /uploadRecipe
    def _upload_recipe(self) -> tuple[Response, int]:
        """
        Uploads a file to the recipes folder, file must be valid JSON.

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        t = load_translation()

        f = request.files['File']
        if f.mimetype != 'application/json':
            return jsonify({'response': 'error', 'message': t['recipe-not-json']}), HTTPStatus.BAD_REQUEST

        try:
            recipe_data = json.load(f.stream)
            recipe_data['fileName'] = f.filename
            MicrolabRecipe.model_validate(recipe_data)
        except ValidationError as err:
            return jsonify({
                'response': 'error',
                'message': t['recipe-error'].format(f, str(err))
            }), HTTPStatus.BAD_REQUEST
        except Exception:
            return jsonify({'response': 'error', 'message': t['json-error']}), HTTPStatus.BAD_REQUEST

        # reading the stream above sets the stream position to EOF, need to go back to start
        f.stream.seek(0)
        f.save(join(config.recipesDirectory, secure_filename(f.filename)))

        return jsonify({'response': 'ok'}), HTTPStatus.OK

    # /deleteRecipe/<name>
    def _delete_recipe(self, name: str) -> tuple[Response, int]:
        """
        Deletes a file in the recipes folder

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """

        t = load_translation()
        recipe = recipes.core.get_recipe_by_name(name)
        try:
            os.remove(join(config.recipesDirectory, secure_filename(recipe.fileName)))
            return jsonify({'response': 'ok'}), HTTPStatus.OK
        except FileNotFoundError:
            return jsonify({'response': 'error', 'message': t['recipe-not-exist']}), HTTPStatus.NOT_FOUND

    # /controllerHardware
    def _get_controller_hardware(self) -> tuple[Response, int]:
        """
        Gets the current controller hardware setting

        :return:
        object
            controllerHardware
                A string with the current controller hardware setting
        """
        return jsonify({'controllerHardware': config.controllerHardware}), HTTPStatus.OK

    # /controllerHardware/list
    def _list_controller_hardware(self) -> Response:
        """
        Gets a list of valid controller hardware settings

        :return:
        list
            a list containing the names of valid controller hardware settings.
            ex: ['pi','AML-S905X-CC-V1.0A']
        """
        file_names = [recipe for recipe in os.listdir(config.controllerHardwareDirectory)]
        configs = list(map(lambda x: x[:-5], filter(lambda x: x.endswith('.yaml'), file_names)))
        return jsonify(configs)

    # /controllerHardware/<name>
    def _select_controller_hardware(self, name: str) -> tuple[Response, int]:
        """
        Sets a new controller hardware setting, and reloads the hardware
        controller to use this

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        config.controllerHardware = name
        self._microlab_interface.reload_config()
        (success, msg) = self._microlab_interface.reload_hardware()
        if success:
            return jsonify({'response': 'ok'}), HTTPStatus.OK
        else:
            return jsonify({'response': 'error', 'message': msg}), HTTPStatus.BAD_REQUEST

    # /uploadControllerConfig
    def _upload_controller_config(self) -> Response:
        """
        Uploads a controller hardware configuration file

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        f = request.files['File']
        f.save(join(config.controllerHardwareDirectory, secure_filename(f.filename)))
        return jsonify({'response': 'ok'})

    # /downloadControllerConfig/<name>
    def _download_controller_config(self, name: str) -> Response:
        """
        Downloads a controller hardware configuration file

        :return:
        The controller configuration file
        """
        file_name = f'{secure_filename(name)}.yaml'
        return send_file(join(config.controllerHardwareDirectory, file_name), name, as_attachment=True)

    # /labHardware
    def _get_lab_hardware(self) -> tuple[Response, int]:
        """
        Gets the current lab hardware setting

        :return:
        object
            labHardware
                A string with the current lab hardware setting
        """
        return jsonify({'labHardware': config.labHardware}), HTTPStatus.OK

    # /labHardware/list
    def _list_lab_hardware(self) -> Response:
        """
        Gets a list of valid lab hardware settings

        :return:
        list
            a list containing the names of valid lab hardware settings.
            ex: ['base_hardware']
        """
        file_names = [recipe for recipe in os.listdir(config.labHardwareDirectory)]
        configs = list(map(lambda x: x[:-5], filter(lambda x: x.endswith('.yaml'), file_names)))
        return jsonify(configs)

    # /labHardware/<name>
    def _select_lab_hardware(self, name: str) -> tuple[Response, int]:
        """
        Sets a new lab hardware setting, and reloads the hardware
        controller to use this

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        config.labHardware = name
        self._microlab_interface.reload_config()
        (success, msg) = self._microlab_interface.reload_hardware()
        if success:
            return jsonify({'response': 'ok'}), HTTPStatus.OK
        else:
            return jsonify({'response': 'error', 'message': msg}), HTTPStatus.BAD_REQUEST

    # /uploadLabConfig
    def _upload_lab_config(self) -> Response:
        """
        Uploads a lab hardware configuration file

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        f = request.files['File']
        f.save(join(config.labHardwareDirectory, secure_filename(f.filename)))
        return jsonify({'response': 'ok'})

    # /downloadLabConfig/<name>
    def _download_lab_config(self, name: str) -> Response:
        """
        Downloads a lab hardware configuration file

        :return:
        The lab configuration file
        """
        file_name = f'{secure_filename(name)}.yaml'
        return send_file(join(config.labHardwareDirectory, file_name), name, as_attachment=True)

    # /reloadHardware
    def _reload_hardware(self) -> tuple[Response, int]:
        """
        Reloads the hardware controller

        :return:
        object
            response
                One of:
                    ok
                    error
            message
                Only present if response is "error" and there is a message to present to the user.
        """
        self._microlab_interface.reload_config()
        (success, msg) = self._microlab_interface.reload_hardware()
        if success:
            return jsonify({'response': 'ok'}), HTTPStatus.OK
        else:
            return jsonify({'response': 'error', 'message': msg}), HTTPStatus.BAD_REQUEST

    # /log
    def _fetch_logs(self) -> tuple[Response, int]:
        """
        Fetches and concatenates the two most recent microlab log files

        :return:
        object
            logs
                The complete log files as a string
        """
        log_file_names = [file for file in glob.glob(os.path.join(config.logDirectory, 'microlab.log*'))]
        log_file_names.sort(key=os.path.getmtime)

        data: str = ''
        for file_name in log_file_names[-2:]:
            data += Path(file_name).read_text()
        return jsonify({'logs': data}), HTTPStatus.OK

    def _register_routes(self):

        # recipes
        self._flask_app.add_api_route('/list', self._list_recipes)
        self._flask_app.add_api_route('/recipe/<name>', self._send_recipe)
        self._flask_app.add_api_route('/uploadRecipe', self._upload_recipe, ['POST'])
        self._flask_app.add_api_route('/deleteRecipe/<name>', self._delete_recipe, ['DELETE'])

        # flow control
        self._flask_app.add_api_route('/start/<name>', self._start, ['POST'])
        self._flask_app.add_api_route('/stop', self._stop, ['POST'])
        self._flask_app.add_api_route('/select/option/<name>', self._select_option, ['POST'])

        # controller hardware
        self._flask_app.add_api_route('/controllerHardware', self._get_controller_hardware)
        self._flask_app.add_api_route('/controllerHardware/list', self._list_controller_hardware)
        self._flask_app.add_api_route('/controllerHardware/<name>', self._select_controller_hardware, ['POST'])
        self._flask_app.add_api_route('/uploadControllerConfig', self._upload_controller_config, ['POST'])
        self._flask_app.add_api_route('/downloadControllerConfig/<name>', self._download_controller_config)

        # lab hardware
        self._flask_app.add_api_route('/labHardware', self._get_lab_hardware)
        self._flask_app.add_api_route('/labHardware/list', self._list_lab_hardware)
        self._flask_app.add_api_route('/labHardware/<name>', self._select_lab_hardware, ['POST'])
        self._flask_app.add_api_route('/uploadLabConfig', self._upload_lab_config, ['POST'])
        self._flask_app.add_api_route('/downloadLabConfig/<name>', self._download_lab_config)
        self._flask_app.add_api_route('/reloadHardware', self._reload_hardware, ['POST'])

        # utils
        self._flask_app.add_api_route('/status', self._status)
        self._flask_app.add_api_route('/log', self._fetch_logs)
