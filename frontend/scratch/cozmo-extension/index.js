// Cozmo Code Lab extension for the pinned Scratch VM. No robot protocol lives here.
const ArgumentType = require('../../extension-support/argument-type');
const BlockType = require('../../extension-support/block-type');
const formatMessage = require('format-message');

const msg = (id, text) => formatMessage({id: `cozmo.${id}`, default: text, description: 'Cozmo Code Lab block'});
const token = new URLSearchParams(window.location.search).get('code_token') || '';
const number = (defaultValue) => ({type: ArgumentType.NUMBER, defaultValue});
const string = (defaultValue) => ({type: ArgumentType.STRING, defaultValue});

class CozmoBlocks {
    constructor (runtime) {
        this.runtime = runtime;
        this.current = null;
        this.previous = null;
        this.lastAnswer = '';
        this.lastError = '';
        this.timer = setInterval(() => this.poll(), 250);
        runtime.on('PROJECT_STOP_ALL', () => this.command('stop', {}));
    }

    async request (path, options = {}) {
        const response = await fetch(path, {
            ...options,
            headers: {'X-Code-Token': token, ...(options.headers || {})}
        });
        const data = await response.json();
        if (!response.ok || data.status === 'error') throw new Error(data.error || 'Cozmo is unavailable.');
        return data;
    }

    async command (command, arguments_) {
        try {
            this.lastError = '';
            return (await this.request('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command, arguments: arguments_})
            })).result;
        } catch (error) {
            this.lastError = error.message;
            console.warn('Cozmo Code Lab:', error.message);
            return null;
        }
    }

    async poll () {
        try {
            const next = (await this.request('/api/state')).state;
            const prev = this.current;
            this.previous = prev;
            this.current = next;
            if (!prev) return;
            const hat = (name, fields) => this.runtime.startHats(`cozmo_${name}`, fields);
            if (next.connected && !prev.connected) hat('whenConnected');
            if (!next.connected && prev.connected) hat('whenDisconnected');
            if (next.picked_up && !prev.picked_up) hat('whenPickedUp');
            if (!next.picked_up && prev.picked_up) hat('whenPutDown');
            if (next.cliff && !prev.cliff) hat('whenCliff');
            if (next.person_visible && !prev.person_visible) hat('whenPerson');
            for (const cube of next.cubes) {
                const old = prev.cubes.find(item => item.number === cube.number);
                const fields = {CUBE: String(cube.number)};
                if (old && cube.tap_sequence > old.tap_sequence) hat('whenCubeTapped', fields);
                if (old && cube.move_sequence > old.move_sequence) hat('whenCubeMoved', fields);
                if (old && cube.connected && !old.connected) hat('whenCubeConnected', fields);
            }
        } catch (error) {
            this.lastError = 'Cozmo lost connection. Check the Wi-Fi connection.';
        }
    }

    getInfo () {
        return {
            id: 'cozmo', name: 'Cozmo', color1: '#087f8c', color2: '#076b75', color3: '#06545c',
            blocks: [
                {opcode: 'move', blockType: BlockType.COMMAND, text: msg('move', 'move [DISTANCE] cm'), arguments: {DISTANCE: number(20)}},
                {opcode: 'turn', blockType: BlockType.COMMAND, text: msg('turn', 'turn [DEGREES] degrees'), arguments: {DEGREES: number(90)}},
                {opcode: 'drive', blockType: BlockType.COMMAND, text: msg('drive', 'drive at [SPEED] for [SECONDS] seconds'), arguments: {SPEED: number(15), SECONDS: number(1)}},
                {opcode: 'stop', blockType: BlockType.COMMAND, text: msg('stop', 'stop Cozmo')},
                {opcode: 'head', blockType: BlockType.COMMAND, text: msg('head', 'set head angle to [ANGLE]'), arguments: {ANGLE: number(20)}},
                {opcode: 'lift', blockType: BlockType.COMMAND, text: msg('lift', 'set lift to [PERCENT] %'), arguments: {PERCENT: number(50)}},
                {opcode: 'expression', blockType: BlockType.COMMAND, text: msg('expression', 'show [EXPRESSION] face'), arguments: {EXPRESSION: {type: ArgumentType.STRING, menu: 'expressions'}}},
                {opcode: 'clearFace', blockType: BlockType.COMMAND, text: msg('clearFace', 'clear face')},
                {opcode: 'say', blockType: BlockType.COMMAND, text: msg('say', 'say [TEXT] and wait'), arguments: {TEXT: string('Hello!')}},
                {opcode: 'sound', blockType: BlockType.COMMAND, text: msg('sound', 'play sound [SOUND]'), arguments: {SOUND: {type: ArgumentType.STRING, menu: 'sounds'}}},
                {opcode: 'animation', blockType: BlockType.COMMAND, text: msg('animation', 'play animation [ANIMATION]'), arguments: {ANIMATION: {type: ArgumentType.STRING, menu: 'animations'}}},
                {opcode: 'cubeColor', blockType: BlockType.COMMAND, text: msg('cubeColor', 'set cube [CUBE] to [COLOR]'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}, COLOR: {type: ArgumentType.STRING, menu: 'colors'}}},
                {opcode: 'whenConnected', blockType: BlockType.EVENT, text: msg('whenConnected', 'when Cozmo connects')},
                {opcode: 'whenDisconnected', blockType: BlockType.EVENT, text: msg('whenDisconnected', 'when Cozmo disconnects')},
                {opcode: 'whenPickedUp', blockType: BlockType.EVENT, text: msg('whenPickedUp', 'when Cozmo is picked up')},
                {opcode: 'whenPutDown', blockType: BlockType.EVENT, text: msg('whenPutDown', 'when Cozmo is put down')},
                {opcode: 'whenCliff', blockType: BlockType.EVENT, text: msg('whenCliff', 'when cliff is detected')},
                {opcode: 'whenPerson', blockType: BlockType.EVENT, text: msg('whenPerson', 'when a person is detected')},
                {opcode: 'whenCubeTapped', blockType: BlockType.EVENT, text: msg('whenCubeTapped', 'when cube [CUBE] is tapped'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}}},
                {opcode: 'whenCubeMoved', blockType: BlockType.EVENT, text: msg('whenCubeMoved', 'when cube [CUBE] moves'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}}},
                {opcode: 'whenCubeConnected', blockType: BlockType.EVENT, text: msg('whenCubeConnected', 'when cube [CUBE] connects'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}}},
                {opcode: 'connected', blockType: BlockType.BOOLEAN, text: msg('connected', 'Cozmo connected?')},
                {opcode: 'battery', blockType: BlockType.REPORTER, text: msg('battery', 'battery level')},
                {opcode: 'pickedUp', blockType: BlockType.BOOLEAN, text: msg('pickedUp', 'Cozmo picked up?')},
                {opcode: 'cliff', blockType: BlockType.BOOLEAN, text: msg('cliff', 'cliff detected?')},
                {opcode: 'cubeConnected', blockType: BlockType.BOOLEAN, text: msg('cubeConnected', 'cube [CUBE] connected?'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}}},
                {opcode: 'cubeTapped', blockType: BlockType.BOOLEAN, text: msg('cubeTapped', 'cube [CUBE] tapped?'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}}},
                {opcode: 'cubeMoving', blockType: BlockType.BOOLEAN, text: msg('cubeMoving', 'cube [CUBE] moving?'), arguments: {CUBE: {type: ArgumentType.NUMBER, menu: 'cubes'}}},
                {opcode: 'personVisible', blockType: BlockType.BOOLEAN, text: msg('personVisible', 'person visible?')},
                {opcode: 'headAngle', blockType: BlockType.REPORTER, text: msg('headAngle', 'head angle')},
                {opcode: 'liftPosition', blockType: BlockType.REPORTER, text: msg('liftPosition', 'lift position')},
                {opcode: 'lastErrorBlock', blockType: BlockType.REPORTER, text: msg('lastError', 'Cozmo message')},
                {opcode: 'askAI', blockType: BlockType.REPORTER, text: msg('askAI', 'ask Cozmo AI [QUESTION]'), arguments: {QUESTION: string('How are you?')}},
                {opcode: 'aiSay', blockType: BlockType.COMMAND, text: msg('aiSay', 'Cozmo AI say [QUESTION]'), arguments: {QUESTION: string('Say hello')}},
                {opcode: 'aiAnswer', blockType: BlockType.REPORTER, text: msg('aiAnswer', 'AI answer')}
            ],
            menus: {
                expressions: {acceptReporters: true, items: ['Happy', 'Sad', 'Angry', 'Surprised', 'Curious', 'Sleepy']},
                sounds: {acceptReporters: true, items: ['happy', 'chirp', 'question', 'grumble', 'sleepy']},
                animations: {acceptReporters: true, items: ['Hello, friend', 'Little celebration', 'Curious glance', 'Sleepy eyes']},
                cubes: {acceptReporters: true, items: ['1', '2', '3']},
                colors: {acceptReporters: true, items: ['red', 'green', 'blue', 'off']}
            }
        };
    }

    move (args) { return this.command('drive_distance', {distance_cm: args.DISTANCE}); }
    turn (args) { return this.command('turn', {degrees: args.DEGREES}); }
    drive (args) { return this.command('drive_timed', {speed: args.SPEED, seconds: args.SECONDS}); }
    stop () { return this.command('stop', {}); }
    head (args) { return this.command('head', {angle: args.ANGLE}); }
    lift (args) { return this.command('lift', {percent: args.PERCENT}); }
    expression (args) { return this.command('expression', {name: args.EXPRESSION}); }
    clearFace () { return this.command('clear_face', {}); }
    say (args) { return this.command('say', {text: String(args.TEXT)}); }
    sound (args) { return this.command('sound', {kind: args.SOUND}); }
    animation (args) { return this.command('animation', {name: args.ANIMATION}); }
    cubeColor (args) { return this.command('cube_color', {cube: args.CUBE, color: args.COLOR}); }
    connected () { return Boolean(this.current && this.current.connected); }
    battery () { return this.current && this.current.battery !== null ? this.current.battery : 0; }
    pickedUp () { return Boolean(this.current && this.current.picked_up); }
    cliff () { return Boolean(this.current && this.current.cliff); }
    cube (args) { return this.current && this.current.cubes.find(item => item.number === Number(args.CUBE)); }
    cubeConnected (args) { const item = this.cube(args); return Boolean(item && item.connected); }
    cubeTapped (args) { const item = this.cube(args); return Boolean(item && item.tapped); }
    cubeMoving (args) { const item = this.cube(args); return Boolean(item && item.moving); }
    personVisible () { return Boolean(this.current && this.current.person_visible); }
    headAngle () { return this.current ? this.current.head_angle : 0; }
    liftPosition () { return this.current ? this.current.lift_position : 0; }
    lastErrorBlock () { return this.lastError; }
    async askAI (args) {
        const answer = await this.command('ai_ask', {question: String(args.QUESTION)});
        this.lastAnswer = answer || '';
        return this.lastAnswer;
    }
    async aiSay (args) {
        const answer = await this.command('ai_say', {question: String(args.QUESTION)});
        this.lastAnswer = answer || '';
    }
    aiAnswer () { return this.lastAnswer; }
}

module.exports = CozmoBlocks;
