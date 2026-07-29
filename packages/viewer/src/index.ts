/**
 * @modumesh/viewer — reusable STL/GLB preview (React Three Fiber).
 *
 * Import this package only from pages that need 3D. Prefer
 * `next/dynamic(..., { ssr: false })` so home/catalog bundles stay light.
 */

export type { ModelFormat, ModelViewerProps, ViewerDimensions } from './types';
export { ModelViewer } from './ModelViewer';
export { formatDimensions } from './math';
