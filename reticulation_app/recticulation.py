import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime

class ReticController(hass.Hass):
    def initialize(self):
        # Import arguements from apps.yaml and store them as class variables
        self.__watering_days = ','.join(self.args['watering_days'])
        #self.log(self.args['watering_days'])
        #self.log(self.__watering_days)
        self.__stations = self.args['stations']
        self.__start_time = self.args['start_time']
        self.__main_valve = self.args['main']
        # Reset valves if app is restarted mid programme
        self.__manual_override = 'off'
        self.turn_off(self.__main_valve)
        for station in self.__stations: self.turn_off(station['valve'])
        for station in self.__stations: self.turn_off(station['manual'])

        # Setup listener for changes in setting from Home Assistant Front End
        for station in self.__stations:
            self.listen_state(self.ManualStart, station['manual'], valve = station['valve'], runtime = station['run_time'])
        self.program_timer = None
        self.program_timer = self.run_daily(self.Program, self.get_state(self.__start_time), constrain_days = self.__watering_days)
        self.listen_state(self.ChangeStartTime, self.__start_time)

    def ManualStart(self, entity, attribute, old, new, kwargs):
        if new == 'on':
            runtime = int(float(self.get_state(kwargs['runtime'])))
            self.log(runtime)
            if self.__manual_override == 'on':
                self.turn_off(entity)
            elif self.__manual_override == 'off':
                self.turn_on(kwargs['valve'])     #Turn on the valve and the main valve
                self.turn_on(self.__main_valve)   # Start timer for duration of runtime 
                self.__manual_override = 'on'
                self.manual_timer = None
                self.manual_timer = self.run_in(self.ManualStop, runtime * 2, valve = kwargs['valve'], manual = entity)
                self.log('Manual timer started')
        elif new == 'off' and self.get_state(kwargs['valve']) == 'on':
            self.turn_off(kwargs['valve'])     #Turn on the valve and the main valve too.
            self.turn_off(self.__main_valve)   #Cancel the manual timer
            self.cancel_timer(self.manual_timer)
            self.__manual_override = 'off'
            self.log('Timer Cancelled')

    def ManualStop(self, kwargs):
        self.turn_off(kwargs['valve'])
        self.turn_off(self.__main_valve)
        self.turn_off(kwargs['manual'])
        self.__manual_override = 'off'
        self.log(f"Station timed off {kwargs['valve']}")

    def ChangeStartTime(self, entity, attribute, old, new, kwargs):
        self.cancel_timer(self.program_timer)
        self.program_timer = None
        self.program_timer = self.run_daily(self.Program, self.get_state(self.__start_time), constrain_days = self.__watering_days)
    
    def Program(self, kwargs):
        now = datetime.strftime(self.datetime(), '%H:%M %p, %a %d %b')
        self.log("Starting new program, at {}".format(now))
        self.__run_squence = [{'switch/turn_on':{"entity_id": self.__main_valve}}]
        for station in self.__stations:
            self.log('for loop')
            if self.get_state(station['active']) == 'on':  #You always need to look out for gettting the state of an entity not just the entity
                runtime = int(float(self.get_state(station['run_time'])))*2
                self.log('{}  {}mins'.format(station['valve'],runtime))
                add_station = [{'switch/turn_on':{"entity_id": station['valve']}},{"sleep": runtime},
                {'switch/turn_off':{"entity_id": station['valve']}}]
                self.__run_squence.extend(add_station)
        self.__run_squence.append({'switch/turn_off':{"entity_id": self.__main_valve}})
        self.log(self.__run_squence)
        self.inline_sequence = self.run_sequence(self.__run_squence)
