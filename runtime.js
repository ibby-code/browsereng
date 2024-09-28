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
    log: function(x) {
        const output = getLogValue(x);
        call_python("log", output);
    }
};

document = {
    querySelectorAll: function(s) {
        var handles = call_python("querySelectorAll", s);
        return handles.map(function(h) { return new Node(h); });
    },
};

function Node(handle) {
    this.handle = handle;
}

Node.prototype.getAttribute = function(attr) {
    return call_python("getAttribute", this.handle, attr);
}