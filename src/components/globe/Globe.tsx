import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";
import { useQuery } from "@tanstack/react-query";
import { propagate } from "@/lib/astrosis/client";
import type { SatelliteRecord, PropagateResponse } from "@/lib/astrosis/types";

const RE = 6371;
const SCALE = 1 / 1000;

function Earth() {
  const r = RE * SCALE;
  return (
    <group>
      <mesh>
        <sphereGeometry args={[r, 48, 32]} />
        <meshStandardMaterial color="#1a2230" roughness={0.95} metalness={0.0} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[r * 1.001, 0.012, 6, 96]} />
        <meshBasicMaterial color="#2a3a4a" />
      </mesh>
      <mesh>
        <torusGeometry args={[r * 1.001, 0.008, 6, 96]} />
        <meshBasicMaterial color="#2a3a4a" />
      </mesh>
    </group>
  );
}

function Axes() {
  const len = RE * SCALE * 1.7;
  return (
    <group>
      <Line p={[0, 0, 0]} q={[len, 0, 0]} color="#3a2020" />
      <Line p={[0, 0, 0]} q={[0, len, 0]} color="#203a20" />
      <Line p={[0, 0, 0]} q={[0, 0, len]} color="#20203a" />
    </group>
  );
}

function Line({
  p,
  q,
  color,
}: {
  p: [number, number, number];
  q: [number, number, number];
  color: string;
}) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute([...p, ...q], 3));
    return g;
  }, [p, q]);
  return (
    <line>
      <primitive attach="geometry" object={geom} />
      <lineBasicMaterial color={color} />
    </line>
  );
}

function Sats({
  sats,
  selectedId,
  onSelect,
}: {
  sats: SatelliteRecord[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const amber = useMemo(() => new THREE.Color("#e8943a"), []);
  const dim = useMemo(() => new THREE.Color("#3a4a5a"), []);
  useFrame(() => {
    const m = ref.current;
    if (!m) return;
    for (let i = 0; i < sats.length; i++) {
      const s = sats[i];
      dummy.position.set(s.pos[0] * SCALE, s.pos[2] * SCALE, -s.pos[1] * SCALE);
      const sel = s.id === selectedId;
      dummy.scale.setScalar(sel ? 0.16 : 0.08);
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
      m.setColorAt(i, sel ? amber : dim);
    }
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.count = sats.length;
  });
  return (
    <instancedMesh
      ref={ref}
      args={[undefined, undefined, Math.max(1, sats.length)]}
      frustumCulled={false}
      onClick={(e) => {
        e.stopPropagation();
        const i = e.instanceId;
        if (i != null) onSelect(sats[i].id);
      }}
    >
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial vertexColors toneMapped={false} />
    </instancedMesh>
  );
}

function OrbitTrace({ positions }: { positions: [number, number, number][] }) {
  const geom = useMemo(() => {
    if (positions.length < 2) return null;
    const points = positions.flat();
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    return g;
  }, [positions]);

  if (!geom) return null;

  return (
    <line>
      <primitive attach="geometry" object={geom} />
      <lineBasicMaterial color="#e8943a" opacity={0.4} transparent />
    </line>
  );
}

function CameraFocus({ target }: { target: [number, number, number] | null }) {
  const controls = useThree((s) => s.controls) as { target: THREE.Vector3 } | null;
  const targetVec = useMemo(
    () => (target ? new THREE.Vector3(target[0], target[1], target[2]) : null),
    [target],
  );
  useFrame(() => {
    if (!targetVec || !controls) return;
    controls.target.lerp(targetVec, 0.05);
  });
  return null;
}

export function Globe({
  satellites,
  selectedId,
  onSelect,
  when,
}: {
  satellites: SatelliteRecord[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  when: Date;
}) {
  const { data: traceData } = useQuery<PropagateResponse>({
    queryKey: ["propagate-trace", selectedId],
    queryFn: ({ signal }) => propagate({ norad: selectedId!, hours: 1.5, dt_seconds: 60 }, signal),
    enabled: selectedId != null,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  });

  const tracePositions = useMemo(() => {
    if (!traceData?.ephemeris) return [];
    return traceData.ephemeris.map(
      (p) => [p.pos[0] * SCALE, p.pos[2] * SCALE, -p.pos[1] * SCALE] as [number, number, number],
    );
  }, [traceData]);

  const selectedSat = useMemo(
    () => satellites.find((s) => s.id === selectedId),
    [satellites, selectedId],
  );

  const focusTarget = useMemo((): [number, number, number] | null => {
    if (!selectedSat) return null;
    return [selectedSat.pos[0] * SCALE, selectedSat.pos[2] * SCALE, -selectedSat.pos[1] * SCALE];
  }, [selectedSat]);

  return (
    <Canvas
      camera={{ position: [14, 9, 14], fov: 42, near: 0.1, far: 800 }}
      dpr={[1, 2]}
      gl={{ antialias: true }}
    >
      <color attach="background" args={["#0a0c0f"]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[15, 8, 12]} intensity={0.9} color="#e8ecf2" />
      <Suspense fallback={null}>
        <Earth />
        <Axes />
        <Sats sats={satellites} selectedId={selectedId} onSelect={onSelect} />
        {tracePositions.length > 0 && <OrbitTrace positions={tracePositions} />}
        {focusTarget && <CameraFocus target={focusTarget} />}
      </Suspense>
      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        minDistance={8}
        maxDistance={60}
        rotateSpeed={0.5}
      />
    </Canvas>
  );
}
