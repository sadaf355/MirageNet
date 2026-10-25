import { useState } from 'react'
import { useEffect } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, Activity, ShieldCheck, Sparkles } from 'lucide-react'
import { HeroScene } from './HeroScene'

export default function WelcomeSplash({ onEnter }: { onEnter: () => void }) {
  const reducedMotion = useReducedMotion() ?? false
  const [showDetails, setShowDetails] = useState(false)
  const [webglAvailable, setWebglAvailable] = useState(true)
  useEffect(() => {
    try {
      const canvas = document.createElement('canvas')
      setWebglAvailable(Boolean(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))))
    } catch { setWebglAvailable(false) }
  }, [])
  return <main className="welcome-splash">
    <div className="welcome-grid-glow" aria-hidden="true" />
    <header className="welcome-top"><div className="brand"><div className="brand-mark"><ShieldCheck size={21}/><span /></div><div><div className="brand-name">mirage<span>net</span></div><div className="brand-caption">DECEPTION OPERATIONS</div></div></div><span className="welcome-environment"><i/> LOCAL SIMULATION · SYNTHETIC DATA ONLY</span></header>
    <section className="welcome-hero">
      <motion.div className="welcome-copy" initial={reducedMotion ? false : {opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:reducedMotion?0:0.55}}>
        <div className="eyebrow"><span className="eyebrow-mark"/> CYBER DECEPTION LAB <span className="eyebrow-divider">/</span> DEMO ENVIRONMENT</div>
        <h1>Make every<br/><span>intrusion tell a story.</span></h1>
        <p>Explore a synthetic enterprise, plant believable decoys, and reconstruct attacker activity from evidence-backed detection events.</p>
        <div className="welcome-actions"><button className="button-primary welcome-enter" onClick={onEnter}>Enter security console <ArrowRight size={16}/></button><button className="button-secondary" onClick={()=>setShowDetails(v=>!v)}><Sparkles size={14}/> What’s inside</button></div>
        {showDetails && <div className="welcome-details"><span><Activity size={14}/> Live synthetic sensor events</span><span><ShieldCheck size={14}/> Incident timelines and ATT&CK context</span><span><Sparkles size={14}/> Decoy lab and evaluation scenarios</span></div>}
        <div className="welcome-disclaimer">Decorative 3D overview only. The live network topology remains in the Cytoscape view.</div>
      </motion.div>
      <motion.div className="welcome-visual" initial={reducedMotion?false:{opacity:0,scale:.98}} animate={{opacity:1,scale:1}} transition={{duration:reducedMotion?0:.7,delay:reducedMotion?0:.12}}>{webglAvailable ? <HeroScene reducedMotion={reducedMotion}/> : <div className="hero-static-fallback" role="img" aria-label="Static illustration of seven simulated network hosts"><div className="hero-static-orbit"><span>WEB-01</span><span>WS-01</span><span>FS-01</span><span>JMP-01</span><span>DB-01</span><span>GIT-01</span><span>BKP-01</span></div><strong>7-NODE SIMULATED NETWORK</strong><small>3D acceleration unavailable · static view</small></div>}</motion.div>
    </section>
    <footer className="welcome-footer"><span><i/> SIMULATION READY</span><span>7 HOSTS · SYNTHETIC DECOYS · EVIDENCE-LED INVESTIGATION</span><button onClick={onEnter}>Skip intro</button></footer>
  </main>
}
