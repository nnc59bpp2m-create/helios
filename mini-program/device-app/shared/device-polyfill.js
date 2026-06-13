// Device polyfill for Zepp OS
// Provides missing globals for shared/message.js

// Polyfill for TextEncoder/TextDecoder
if (typeof TextEncoder === 'undefined') {
  global.TextEncoder = class TextEncoder {
    encode(str) {
      const utf8 = unescape(encodeURIComponent(str))
      const result = new Uint8Array(utf8.length)
      for (let i = 0; i < utf8.length; i++) {
        result[i] = utf8.charCodeAt(i)
      }
      return result
    }
  }
}

if (typeof TextDecoder === 'undefined') {
  global.TextDecoder = class TextDecoder {
    decode(buffer) {
      let str = ''
      for (let i = 0; i < buffer.length; i++) {
        str += String.fromCharCode(buffer[i])
      }
      return decodeURIComponent(escape(str))
    }
  }
}

// Polyfill for Promise
if (typeof Promise === 'undefined') {
  global.Promise = require('promise-polyfill')
}

// Polyfill for Map
if (typeof Map === 'undefined') {
  global.Map = require('es6-map')
}

// Polyfill for setTimeout/clearTimeout
if (typeof setTimeout === 'undefined') {
  global.setTimeout = (fn, ms) => {
    return timer.createTimer(fn, ms, false)
  }
}

if (typeof clearTimeout === 'undefined') {
  global.clearTimeout = (id) => {
    timer.stopTimer(id)
  }
}

// Polyfill for console
if (typeof console === 'undefined') {
  global.console = {
    log: (...args) => { hmUI.showToast({ text: args.join(' ') }) },
    error: (...args) => { hmUI.showToast({ text: 'Error: ' + args.join(' ') }) },
    warn: (...args) => {},
    info: (...args) => {}
  }
}

module.exports = {}