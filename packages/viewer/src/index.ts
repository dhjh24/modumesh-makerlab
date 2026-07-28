/** Viewer placeholder — will integrate Three.js / React Three Fiber. */

export type ModelFormat = 'stl' | 'glb' | 'obj' | 'step';

export interface ViewerProps {
  src: string;
  format: ModelFormat;
  width?: number;
  height?: number;
}

export function createViewer(container: HTMLElement, props: ViewerProps): void {
  console.log('Viewer placeholder:', props.src);
}
