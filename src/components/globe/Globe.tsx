import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";
import type { SatelliteRecord } from "@/lib/astrosis/types";

const RE = 6371;
const SCALE = 1 / 1000;

function Earth() {
  const g = useRef<THREE.Group>(null);
  useFrame((_, dt) => { if (g.current) g.current.rotation.y += dt * 0.015; });
  const r = RE * SCALE;
  return (
    <group ref={g}>
      <mesh>
        <sphereGeometry args={[r, 48, 32]} />
        <meshStandardMaterial color="#1a2128" roughness={0.95} metalness={0.0} />
      </mesh>
      {/* Equator ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[r * 1.001, 0.012, 6, 96]} />
        <meshBasicMaterial color="#3d4651" />
      </mesh>
      {/* Prime meridian */}
      <mesh>
        <torusGeometry args={[r * 1.001, 0.008, 6, 96]} />
        <meshBasicMaterial color="#2a3138" />
      </mesh>
    </group>
  );
}

function Axes() {
  const len = RE * SCALE * 1.7;
  return (
    <group>
      <Line p={[0,0,0]} q={[len,0,0]} color="#5a6470" />
      <Line p={[0,0,0]} q={[0,len,0]} color="#5a6470" />
      <Line p={[0,0,0]} q={[0,0,len]} color="#5a6470" />
    </group>
  );
}
function Line({ p, q, color }: { p: [number,number,number]; q: [number,number,number]; color: string }) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute([...p, ...q], 3));
    return g;
  }, [p, q]);
  return <line><primitive attach="geometry" object={geom} /><lineBasicMaterial color={color} /></line>;
}

function Sats({ sats, selectedId, onSelect }: { sats: SatelliteRecord[]; selectedId: number | null; onSelect: (id: number) => void }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const amber = useMemo(() => new THREE.Color("#e9a23b"), []);
  const dim = useMemo(() => new THREE.Color("#a8b1bc"), []);
  useFrame(() => {
    const m = ref.current;
    if (!m) return;
    for (let i = 0; i < sats.length; i++) {
      const s = sats[i];
      dummy.position.set(s.pos[0] * SCALE, s.pos[2] * SCALE, -s.pos[1] * SCALE);
      const sel = s.id === selectedId;
      dummy.scale.setScalar(sel ? 0.25 : 0.085);
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
      onClick={(e) => { e.stopPropagation(); const i = e.instanceId; if (i != null) onSelect(sats[i].id); }}
    >
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial vertexColors toneMapped={false} />
    </instancedMesh>
  );
}

export function Globe({ satellites, selectedId, onSelect }: { satellites: SatelliteRecord[]; selectedId: number | null; onSelect: (id: number) => void }) {
  return (
    <Canvas camera={{ position: [14, 9, 14], fov: 42, near: 0.1, far: 800 }} dpr={[1, 2]} gl={{ antialias: true }}>
      <color attach="background" args={["#1a1d22"]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[15, 8, 12]} intensity={0.9} color="#e8ecf2" />
      <Suspense fallback={null}>
        <Earth />
        <Axes />
        <Sats sats={satellites} selectedId={selectedId} onSelect={onSelect} />
      </Suspense>
      <OrbitControls enableDamping dampingFactor={0.08} minDistance={8} maxDistance={60} rotateSpeed={0.5} />
    </Canvas>
  );
}