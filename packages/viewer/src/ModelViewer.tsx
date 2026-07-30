import { Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import {
  Bounds,
  Center,
  GizmoHelper,
  GizmoViewport,
  Grid,
  OrbitControls,
  useGLTF,
} from '@react-three/drei';
import {
  Box3,
  BoxHelper,
  Color,
  DoubleSide,
  Group,
  Mesh,
  MeshStandardMaterial,
  type BufferGeometry,
} from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { boxToDimensions, formatDimensions } from './math';
import type { ModelFormat, ModelViewerProps, ViewerDimensions } from './types';

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.('change', update);
    return () => mq.removeEventListener?.('change', update);
  }, []);
  return reduced;
}

function applyWireframe(root: Group, wireframe: boolean) {
  root.traverse((obj) => {
    const mesh = obj as Mesh;
    if (!mesh.isMesh) return;
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const mat of materials) {
      const std = mat as MeshStandardMaterial;
      if (std && 'wireframe' in std) std.wireframe = wireframe;
    }
  });
}

function StlModel({
  src,
  wireframe,
  onReady,
  onError,
}: {
  src: string;
  wireframe: boolean;
  onReady: (group: Group) => void;
  onError: (message: string) => void;
}) {
  const [geometry, setGeometry] = useState<BufferGeometry | null>(null);
  const groupRef = useRef<Group>(null);

  useEffect(() => {
    let cancelled = false;
    const loader = new STLLoader();
    loader.load(
      src,
      (geo) => {
        if (cancelled) return;
        geo.computeVertexNormals();
        setGeometry(geo);
      },
      undefined,
      (err) => {
        if (!cancelled) onError(err instanceof Error ? err.message : 'Failed to load STL.');
      },
    );
    return () => {
      cancelled = true;
    };
  }, [src, onError]);

  useLayoutEffect(() => {
    if (geometry && groupRef.current) onReady(groupRef.current);
  }, [geometry, onReady]);

  if (!geometry) return null;

  return (
    <group ref={groupRef}>
      <mesh geometry={geometry} castShadow receiveShadow>
        <meshStandardMaterial
          color="#1f8a7a"
          metalness={0.15}
          roughness={0.45}
          wireframe={wireframe}
          side={DoubleSide}
        />
      </mesh>
    </group>
  );
}

function GlbModel({
  src,
  wireframe,
  onReady,
}: {
  src: string;
  wireframe: boolean;
  onReady: (group: Group) => void;
}) {
  const gltf = useGLTF(src);
  const groupRef = useRef<Group>(null);

  useLayoutEffect(() => {
    const root = groupRef.current;
    if (!root) return;
    applyWireframe(root, wireframe);
    onReady(root);
  }, [gltf, wireframe, onReady]);

  return (
    <group ref={groupRef}>
      <primitive object={gltf.scene.clone(true)} />
    </group>
  );
}

function ModelScene({
  src,
  format,
  wireframe,
  showBuildPlate,
  showBoundingBox,
  onDimensions,
  onError,
}: {
  src: string;
  format: ModelFormat;
  wireframe: boolean;
  showBuildPlate: boolean;
  showBoundingBox: boolean;
  onDimensions?: (dims: ViewerDimensions) => void;
  onError: (message: string) => void;
}) {
  const helperRef = useRef<BoxHelper | null>(null);
  const groupHolder = useRef<Group | null>(null);

  const handleReady = (group: Group) => {
    groupHolder.current = group;
    try {
      const box = new Box3().setFromObject(group);
      if (box.isEmpty()) {
        onError('Model bounds are empty.');
        return;
      }
      onDimensions?.(boxToDimensions(box));

      if (helperRef.current) {
        helperRef.current.removeFromParent();
        helperRef.current.dispose();
        helperRef.current = null;
      }
      if (showBoundingBox) {
        const helper = new BoxHelper(group, new Color('#0b3d4a'));
        group.parent?.add(helper);
        helperRef.current = helper;
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to measure model.');
    }
  };

  useEffect(() => {
    return () => {
      if (helperRef.current) {
        helperRef.current.removeFromParent();
        helperRef.current.dispose();
      }
    };
  }, []);

  useEffect(() => {
    const group = groupHolder.current;
    if (!group) return;
    if (helperRef.current) {
      helperRef.current.removeFromParent();
      helperRef.current.dispose();
      helperRef.current = null;
    }
    if (showBoundingBox) {
      const helper = new BoxHelper(group, new Color('#0b3d4a'));
      group.parent?.add(helper);
      helperRef.current = helper;
    }
  }, [showBoundingBox]);

  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[40, 60, 30]} intensity={1.1} castShadow />
      <directionalLight position={[-30, 20, -20]} intensity={0.35} />

      <Bounds fit clip observe margin={1.35}>
        <Center>
          {format === 'stl' ? (
            <StlModel src={src} wireframe={wireframe} onReady={handleReady} onError={onError} />
          ) : (
            <GlbModel src={src} wireframe={wireframe} onReady={handleReady} />
          )}
        </Center>
      </Bounds>

      {showBuildPlate ? (
        <Grid
          args={[120, 120]}
          cellSize={5}
          cellThickness={0.6}
          cellColor="#9eb6b1"
          sectionSize={20}
          sectionThickness={1.1}
          sectionColor="#3d6b64"
          fadeDistance={180}
          fadeStrength={1}
          infiniteGrid={false}
        />
      ) : null}
    </>
  );
}

export function ModelViewer({
  src,
  format,
  className = '',
  showBuildPlate = true,
  showBoundingBox = true,
  wireframe: wireframeProp = false,
  onDimensions,
  onError,
  ariaLabel = '3D model viewer',
}: ModelViewerProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [wireframe, setWireframe] = useState(wireframeProp);
  const [plate, setPlate] = useState(showBuildPlate);
  const [bbox, setBbox] = useState(showBoundingBox);
  const [dims, setDims] = useState<ViewerDimensions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controlsRef = useRef<OrbitControlsImpl | null>(null);

  useEffect(() => setWireframe(wireframeProp), [wireframeProp]);
  useEffect(() => setPlate(showBuildPlate), [showBuildPlate]);
  useEffect(() => setBbox(showBoundingBox), [showBoundingBox]);
  useEffect(() => {
    setDims(null);
    setError(null);
  }, [src, format]);

  const handleDims = (d: ViewerDimensions) => {
    setDims(d);
    onDimensions?.(d);
  };

  const handleError = (message: string) => {
    setError(message);
    onError?.(message);
  };

  const resetCamera = () => {
    const controls = controlsRef.current;
    if (!controls) return;
    controls.reset();
    controls.target.set(0, 0, 0);
    controls.update();
  };

  return (
    <div className={`mm-viewer ${className}`.trim()}>
      <div className="mm-viewer__toolbar" role="toolbar" aria-label="Viewer controls">
        <button type="button" className="mm-viewer__tool" onClick={resetCamera}>
          Reset camera
        </button>
        <button
          type="button"
          className="mm-viewer__tool"
          aria-pressed={wireframe}
          onClick={() => setWireframe((v) => !v)}
        >
          Wireframe
        </button>
        <button
          type="button"
          className="mm-viewer__tool"
          aria-pressed={plate}
          onClick={() => setPlate((v) => !v)}
        >
          Build plate
        </button>
        <button
          type="button"
          className="mm-viewer__tool"
          aria-pressed={bbox}
          onClick={() => setBbox((v) => !v)}
        >
          Bounding box
        </button>
      </div>

      <div className="mm-viewer__canvas-wrap" role="img" aria-label={ariaLabel}>
        <Canvas
          shadows
          dpr={reducedMotion ? [1, 1] : [1, 1.75]}
          camera={{ position: [45, 35, 55], fov: 42, near: 0.1, far: 2000 }}
          gl={{ antialias: !reducedMotion }}
          onCreated={({ gl }) => {
            gl.setClearColor(new Color('#e7eef0'));
          }}
        >
          <Suspense fallback={null}>
            <ModelScene
              src={src}
              format={format}
              wireframe={wireframe}
              showBuildPlate={plate}
              showBoundingBox={bbox}
              onDimensions={handleDims}
              onError={handleError}
            />
          </Suspense>
          <OrbitControls
            ref={controlsRef}
            makeDefault
            enableDamping={!reducedMotion}
            dampingFactor={0.08}
            enablePan
            enableZoom
            enableRotate
          />
          {!reducedMotion ? (
            <GizmoHelper alignment="bottom-right" margin={[56, 56]}>
              <GizmoViewport axisColors={['#c45c4a', '#3d8b6e', '#3b6ea8']} labelColor="#1a2b2e" />
            </GizmoHelper>
          ) : null}
        </Canvas>
      </div>

      <div className="mm-viewer__status" aria-live="polite">
        {error ? (
          <span className="mm-viewer__err">{error}</span>
        ) : dims ? (
          <span>Dimensions: {formatDimensions(dims)}</span>
        ) : (
          <span>Loading model…</span>
        )}
        <span className="mm-viewer__hint">Drag to rotate · scroll to zoom · right-drag to pan</span>
      </div>
    </div>
  );
}
