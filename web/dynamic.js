import { app } from "../../scripts/app.js";

function mimicNode(node, target, slot) {
  const getWidget = (widget) => {
    if (typeof widget.origType === "undefined") return widget;
    const newWidget = new Proxy(widget, {
      has(target, prop) {
        return prop in target && prop !== "origType" && prop !== "computeSize";
      },
      get(target, prop) {
        if (prop.startsWith("orig") || prop === "computeSize") {
          return undefined;
        } else if (prop === "type") {
          return target.origType;
        } else if (prop === "name") {
          return inputName;
        } else {
          return target[prop];
        }
      },
      set(target, prop, value) {
        target[prop] = value;
        return true;
      }
    });
    return newWidget;
  }
  const input = target.inputs[slot];
  const inputName = node.inputs.length > 0 ? node.inputs[0].name : node.widgets[0].name;
  if (typeof input.widget === "undefined") {  // This is an input
    node.inputs = [{ ...input, name: inputName }];
    node.widgets = [];
  } else {  // This is a widget
    node.widgets = [getWidget(target.widgets.find(w => w.name === input.name))];
    node.inputs = [];
    node.size = node.computeSize();
    requestAnimationFrame(() => {
      if (node.onResize) {
        node.onResize(node.size);
      }
    });
  }
}

app.registerExtension({
	name: "Comfy.DynamicInput",
  dynamicNodes: ["CPackInputAny", "CPackInputFile"],

	async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!this.dynamicNodes.includes(nodeData.name)) return;

    nodeType.prototype.onConnectOutput = function () {
      if (this.outputs[0].links?.length > 0) return false;
      const target = arguments[3];
      if (this.type === "CPackInputFile" && !["COMBO", "STRING"].includes(target.inputs[arguments[4]].type))
        return false;
      mimicNode(this, target, arguments[4]);
      this.title = target.inputs[arguments[4]].name;
    }
  },

  async setup(app) {
    app.graph.nodes.forEach((node) => {
      if (!this.dynamicNodes.includes(node.type)) return;
      if (node.outputs.length > 0 && node.outputs[0].links.length > 0) {
        const link = node.graph.links[node.outputs[0].links[0]];
        mimicNode(node, app.graph.getNodeById(link.target_id), link.target_slot);
      }
    })
  },

  async init(app) {
    const originalToPrompt = app.graphToPrompt;
    const self = this;
    app.graphToPrompt = async function(graph = app.graph, clean = true) {
      const { workflow, output } = await originalToPrompt(graph, clean);
      Object.entries(output).forEach(([id, nodeData]) => {
        if (!nodeData.class_type.startsWith("CPackInput")) return;
        const node = graph.getNodeById(parseInt(id));
        if (!nodeData["_meta"]) {
          nodeData["_meta"] = { title: node.title };
        }
        if (node.widgets.length === 0) return;
        const widget = node.widgets[0];
        nodeData["_meta"] = { ...nodeData["_meta"], options: widget.options };
      });
      return { workflow, output };
    };
  }
});
