export type ModelFormat = 'stl' | 'glb';

export interface ViewerDimensions {
  width: number;
  height: number;
  depth: number;
  unit: string;
}

export interface ModelViewerProps {
  /** URL or blob URL to the model. */
  src: string;
  format: ModelFormat;
  className?: string;
  /** Show a build-plate style ground grid. Default true. */
  showBuildPlate?: boolean;
  /** Show world-axis-aligned bounding box. Default true. */
  showBoundingBox?: boolean;
  /** Initial wireframe mode. */
  wireframe?: boolean;
  /** Called when dimensions are computed after load. */
  onDimensions?: (dims: ViewerDimensions) => void;
  /** Called when loading fails. */
  onError?: (message: string) => void;
  /** Accessible label for the canvas region. */
  ariaLabel?: string;
}
