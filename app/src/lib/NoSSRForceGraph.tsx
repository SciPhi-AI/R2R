import React, { forwardRef, useImperativeHandle, useRef } from 'react';
import ForceGraph2D, {
  ForceGraphProps,
  ForceGraphMethods,
  NodeObject,
  LinkObject,
} from 'react-force-graph-2d';

interface NoSSRForceGraphProps extends Omit<ForceGraphProps, 'graphData'> {
  data: {
    nodes: NodeObject[];
    links: LinkObject[];
  };
}

export interface NoSSRForceGraphRef {
  zoomToFit: (duration?: number) => void;
  zoomTo: (zoomLevel: number, duration?: number) => void;
}

const NoSSRForceGraph = forwardRef<NoSSRForceGraphRef, NoSSRForceGraphProps>(
  (props, ref) => {
    const forceGraphRef = useRef<ForceGraphMethods>();

    useImperativeHandle(ref, () => ({
      zoomToFit: (duration) => {
        forceGraphRef.current?.zoomToFit(duration);
      },
      zoomTo: (zoomLevel, duration) => {
        forceGraphRef.current?.zoom(zoomLevel, duration);
      },
    }));

    return (
      <ForceGraph2D
        ref={forceGraphRef as React.MutableRefObject<ForceGraphMethods>}
        graphData={props.data}
        {...props}
      />
    );
  }
);

NoSSRForceGraph.displayName = 'NoSSRForceGraph';

export default NoSSRForceGraph;
