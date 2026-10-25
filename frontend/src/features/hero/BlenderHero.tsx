import { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { Environment, Float, useGLTF } from '@react-three/drei'

function HeroModel() {
  const { scene } = useGLTF('/models/hero.glb')
  return <Float speed={0.35} rotationIntensity={0.04} floatIntensity={0.04}><primitive object={scene} scale={1.8} /></Float>
}

/** Optional Route B renderer. Place the exported Blender asset at public/models/hero.glb. */
export function BlenderHero() {
  return <div className="hero-canvas" role="img" aria-label="Blender-rendered MirageNet network island">
    <Canvas camera={{ position: [0, 2.6, 7], fov: 40 }}>
      <ambientLight intensity={1.2} /><directionalLight position={[4, 6, 5]} intensity={2} />
      <Suspense fallback={null}><HeroModel /><Environment preset="city" /></Suspense>
    </Canvas>
  </div>
}
