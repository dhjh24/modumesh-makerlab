import { Box3, Vector3 } from 'three';
import type { ViewerDimensions } from './types';

export function boxToDimensions(box: Box3, unit = 'mm'): ViewerDimensions {
  const size = new Vector3();
  box.getSize(size);
  return {
    width: Math.abs(size.x),
    height: Math.abs(size.y),
    depth: Math.abs(size.z),
    unit,
  };
}

export function formatDimensions(dims: ViewerDimensions, digits = 2): string {
  const f = (n: number) => n.toFixed(digits);
  return `${f(dims.width)} × ${f(dims.height)} × ${f(dims.depth)} ${dims.unit}`;
}
