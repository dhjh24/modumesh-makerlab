import dynamic from 'next/dynamic';
import type { ComponentProps } from 'react';
import { LoadingState } from '@modumesh/ui';

/**
 * Lazy 3D viewer — keeps Three.js / R3F out of the home and catalog bundles.
 */
export const LazyModelViewer = dynamic(
  () => import('@modumesh/viewer').then((m) => m.ModelViewer),
  {
    ssr: false,
    loading: () => (
      <LoadingState title="Loading viewer…" description="Preparing the 3D preview module." />
    ),
  },
);

export type LazyModelViewerProps = ComponentProps<typeof LazyModelViewer>;
