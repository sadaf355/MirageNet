import { useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Float, Stars } from '@react-three/drei'
import * as THREE from 'three'

const NODES = [
  { name: 'WEB-01', p: [-2.1, 0.25, 0.3] as [number, number, number], color: '#55e6c1' },
  { name: 'WS-01', p: [-1.1, 0.85, -0.5] as [number, number, number], color: '#55e6c1' },
  { name: 'FS-01', p: [-0.1, 0.35, 0.8] as [number, number, number], color: '#8ab9ff' },
  { name: 'JMP-01', p: [0.15, 1.05, -0.35] as [number, number, number], color: '#ff6471' },
  { name: 'DB-01', p: [1.2, 0.3, 0.5] as [number, number, number], color: '#ff6471' },
  { name: 'GIT-01', p: [1.45, 0.9, -0.6] as [number, number, number], color: '#8ab9ff' },
  { name: 'BKP-01', p: [2.1, 0.35, 0.1] as [number, number, number], color: '#e7b86d' },
]
const EDGES = [[0,1],[1,2],[1,3],[2,6],[3,4],[3,5],[3,6]] as const

function NetworkIsland({ reducedMotion }: { reducedMotion: boolean }) {
  const island = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (!reducedMotion && island.current) island.current.rotation.y += delta * 0.11
  })
  return <group ref={island}>
    <mesh position={[0, -0.2, 0]}>
      <cylinderGeometry args={[2.85, 3.2, 0.35, 7, 1]} />
      <meshStandardMaterial color="#142536" metalness={0.65} roughness={0.34} flatShading />
    </mesh>
    <mesh position={[0, -0.015, 0]}>
      <cylinderGeometry args={[2.55, 2.8, 0.06, 7, 1]} />
      <meshStandardMaterial color="#0e1b29" metalness={0.5} roughness={0.45} />
    </mesh>
    <mesh position={[0, 0.1, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <torusGeometry args={[2.55, 0.018, 8, 90]} />
      <meshBasicMaterial color="#55e6c1" transparent opacity={0.7} />
    </mesh>
    <group>
      {EDGES.map(([a,b]) => {
        const start = new THREE.Vector3(...NODES[a].p)
        const end = new THREE.Vector3(...NODES[b].p)
        const mid = start.clone().add(end).multiplyScalar(0.5)
        const direction = end.clone().sub(start)
        return <mesh key={`${a}-${b}`} position={mid.toArray()} quaternion={new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0), direction.clone().normalize())}>
          <cylinderGeometry args={[0.012, 0.012, direction.length(), 6]} />
          <meshBasicMaterial color="#3d9f91" transparent opacity={0.8} />
        </mesh>
      })}
    </group>
    {NODES.map((node, i) => <group key={node.name} position={node.p}>
      <Float speed={reducedMotion ? 0 : 1.2 + i * 0.08} rotationIntensity={reducedMotion ? 0 : 0.08} floatIntensity={reducedMotion ? 0 : 0.12}>
        <mesh>
          <icosahedronGeometry args={[0.19, 1]} />
          <meshStandardMaterial color={node.color} emissive={node.color} emissiveIntensity={0.7} metalness={0.35} roughness={0.25} />
        </mesh>
        <mesh scale={1.55}>
          <sphereGeometry args={[0.19, 16, 16]} />
          <meshBasicMaterial color={node.color} transparent opacity={0.08} />
        </mesh>
      </Float>
    </group>)}
  </group>
}

export function HeroScene({ reducedMotion = false }: { reducedMotion?: boolean }) {
  return <div className="hero-canvas" aria-label="Decorative 3D illustration of a seven-host simulated network" role="img">
    <Canvas camera={{ position: [0, 3.2, 7.4], fov: 42 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={1.25} />
      <directionalLight position={[4, 6, 5]} intensity={2.2} color="#b4fff0" />
      <pointLight position={[-4, 2, -3]} intensity={1.2} color="#2d88a5" />
      {!reducedMotion && <Stars radius={18} depth={8} count={550} factor={1.6} saturation={0} fade speed={0.2} />}
      <NetworkIsland reducedMotion={reducedMotion} />
    </Canvas>
    <div className="hero-canvas-caption"><span className="status-dot good" /> 7 NODES <i /> SIMULATED TRUST GRAPH</div>
  </div>
}
