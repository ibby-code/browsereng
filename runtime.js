console = {
    log: function(x) {
        var x_type = typeof x;
        var output = ""
        switch (x_type) {
            case "boolean":
            case "number":
            case "string":
                output = x;
                break
            default:
                output = "[Object object]";
                break;
        }
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