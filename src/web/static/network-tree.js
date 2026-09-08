(function () {
  var dataScript = document.getElementById("network-tree-data");
  var container = document.getElementById("network-tree-chart");
  if (!dataScript || !container || typeof d3 === "undefined") {
    return;
  }

  var data = JSON.parse(dataScript.textContent);
  if (!data) {
    return;
  }

  var COLOR_ACTIVE = "#365c80";
  var COLOR_INACTIVE = "#c0392b";
  var COLOR_LINK = "#b9c6d3";
  var NODE_RADIUS = 7;
  var LEVEL_HEIGHT = 130;
  var SIBLING_GAP = 150;

  var width = container.clientWidth || 900;
  var height = 560;

  var svg = d3
    .select(container)
    .append("svg")
    .attr("width", "100%")
    .attr("height", height)
    .attr("viewBox", [0, 0, width, height]);

  var viewport = svg.append("g");

  svg.call(
    d3
      .zoom()
      .scaleExtent([0.3, 2.5])
      .on("zoom", function (event) {
        viewport.attr("transform", event.transform);
      })
  );

  var root = d3.hierarchy(data);
  root.x0 = width / 2;
  root.y0 = 0;
  root.children.forEach(collapse);

  var linkGroup = viewport.append("g").attr("class", "network-links");
  var nodeGroup = viewport.append("g").attr("class", "network-nodes");

  update(root);

  function collapse(node) {
    if (node.children) {
      node._children = node.children;
      node._children.forEach(collapse);
      node.children = null;
    }
  }

  function update(source) {
    var treeLayout = d3.tree().nodeSize([SIBLING_GAP + NODE_RADIUS * 2, LEVEL_HEIGHT]);
    treeLayout(root);

    var nodes = root.descendants();
    var links = root.links();

    nodes.forEach(function (node) {
      node.y = node.depth * LEVEL_HEIGHT + 40;
    });

    var minX = d3.min(nodes, function (node) {
      return node.x;
    });
    var maxX = d3.max(nodes, function (node) {
      return node.x;
    });
    var centerOffset = width / 2 - (minX + maxX) / 2;

    var link = linkGroup
      .selectAll("path.network-link")
      .data(links, function (d) {
        return d.target.data.id;
      });

    link
      .enter()
      .append("path")
      .attr("class", "network-link")
      .attr("fill", "none")
      .attr("stroke", COLOR_LINK)
      .attr("stroke-width", 1.5)
      .merge(link)
      .attr("d", function (d) {
        return linkPath(d.source, d.target, centerOffset);
      });

    link.exit().remove();

    var node = nodeGroup
      .selectAll("g.network-node")
      .data(nodes, function (d) {
        return d.data.id;
      });

    var nodeEnter = node
      .enter()
      .append("g")
      .attr("class", "network-node")
      .attr(
        "transform",
        "translate(" + (source.x0 + centerOffset) + "," + source.y0 + ")"
      )
      .on("click", function (_event, d) {
        if (d.children) {
          d._children = d.children;
          d.children = null;
        } else if (d._children) {
          d.children = d._children;
          d._children = null;
        } else {
          return;
        }
        update(d);
      });

    nodeEnter
      .append("circle")
      .attr("r", NODE_RADIUS)
      .attr("fill", function (d) {
        return d.data.is_active ? COLOR_ACTIVE : COLOR_INACTIVE;
      })
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);

    nodeEnter
      .append("text")
      .attr("dy", "0.32em")
      .attr("x", function (d) {
        return d._children || d.children ? -(NODE_RADIUS + 6) : NODE_RADIUS + 6;
      })
      .attr("text-anchor", function (d) {
        return d._children || d.children ? "end" : "start";
      })
      .attr("fill", "#27374a")
      .attr("font-size", "13px")
      .attr("font-family", "inherit")
      .text(function (d) {
        return d.data.name;
      });

    nodeEnter
      .filter(function (d) {
        return !!(d._children || d.children);
      })
      .append("circle")
      .attr("class", "network-toggle-ring")
      .attr("r", NODE_RADIUS + 4)
      .attr("fill", "none")
      .attr("stroke", COLOR_LINK)
      .attr("stroke-width", 1);

    var nodeUpdate = nodeEnter.merge(node);
    nodeUpdate
      .transition()
      .duration(220)
      .attr("transform", function (d) {
        return "translate(" + (d.x + centerOffset) + "," + d.y + ")";
      });

    var nodeExit = node
      .exit()
      .transition()
      .duration(220)
      .attr(
        "transform",
        "translate(" + (source.x + centerOffset) + "," + source.y + ")"
      )
      .remove();
    nodeExit.select("circle").attr("r", 1e-6);
    nodeExit.select("text").attr("fill-opacity", 1e-6);

    nodes.forEach(function (d) {
      d.x0 = d.x;
      d.y0 = d.y;
    });
  }

  function linkPath(source, target, centerOffset) {
    var sx = source.x + centerOffset;
    var sy = source.y;
    var tx = target.x + centerOffset;
    var ty = target.y;
    var midY = (sy + ty) / 2;
    return "M" + sx + "," + sy + "C" + sx + "," + midY + " " + tx + "," + midY + " " + tx + "," + ty;
  }
})();
