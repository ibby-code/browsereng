function getLogValue(x) {
    var x_type = typeof x;
    var output = ""
    switch (x_type) {
        case "boolean":
        case "number":
            output = x;
            break
        case "string":
            output = "\"" + x  + "\"";
            break
        default:
            if (Array.isArray(x)) {
                output += "[";
                for (var i = 0; i < x.length; i++) {
                    output += " " + getLogValue(x[i]) + ",";
                }
                if (x.length) {
                    output = output.slice(0, -1); 
                }
                output += "]";
            } else {
                output = "[Object object]";
            }
            break;
    }
    return output;
}

console = {
    log: function() {
        var values = [];
        for (var i = 0; i < arguments.length; i++) {
            values.push(getLogValue(arguments[i]));
        }
        call_python("log", values.join(" "));
    }
};

document = {
    querySelectorAll: function(s) {
        var handles = call_python("querySelectorAll", s);
        return handles.map(function(h) { return new Node(h); });
    },
};

LISTENERS = {}

function Node(handle) {
    this.handle = handle;
}

Object.defineProperty(Node.prototype, 'innerHTML', {
    set: function(s) {
        call_python("innerHTML_set", this.handle, s.toString());
    }
});

Object.defineProperty(Node.prototype, 'value', {
    get: function() {
        return call_python("value_get", this.handle);
    }
});

Node.prototype.getAttribute = function(attr) {
    return call_python("getAttribute", this.handle, attr);
}

Node.prototype.addEventListener = function(type, listener) {
    if (!LISTENERS[this.handle]) LISTENERS[this.handle] = {};
    var dict = LISTENERS[this.handle];
    if (!dict[type]) dict[type] = [];
    var list = dict[type];
    list.push(listener);
}

Node.prototype.dispatchEvent = function(evt) {
    var type = evt.type;
    var handle = this.handle;
    var list =  (LISTENERS[handle] && LISTENERS[handle][type]) || [];
    for (var i = 0; i < list.length; i++) {
        list[i].call(this, evt)
    }
    return evt.defaultEnabled;
}

function Event(type, value) {
    this.type = type;
    this.value = value;
    this.defaultEnabled = true;
}

Event.prototype.preventDefault = function() {
    this.defaultEnabled = false;
}
