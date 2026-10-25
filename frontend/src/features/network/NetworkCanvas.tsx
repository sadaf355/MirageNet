import { useEffect, useRef } from 'react'
import cytoscape, { type Core } from 'cytoscape'
import type { Network } from '../../services/api'

export function NetworkCanvas({network,filter='',compact=false,onOpen,onHostSelect,onEdgeSelect}:{network:Network|null;filter?:string;compact?:boolean;onOpen?:()=>void;onHostSelect?:(host:{id:string;hostname:string;role:string;zone:string})=>void;onEdgeSelect?:(edge:{source:string;target:string})=>void}) {
  const ref = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core|null>(null)
  useEffect(() => {
    if (!ref.current || !network) return
    cyRef.current?.destroy()
    const positions: Record<string,{x:number;y:number}> = {
      'web-01':{x:75,y:145}, 'ws-01':{x:240,y:145}, 'fs-01':{x:405,y:70},
      'jmp-01':{x:405,y:220}, 'db-01':{x:590,y:70}, 'git-01':{x:590,y:155}, 'bkp-01':{x:590,y:245}
    }
    const elements: cytoscape.ElementDefinition[] = [
      ...network.nodes.map(n=>({data:{id:n.id,label:n.hostname,role:n.role,zone:n.zone,value:n.data_value,status:n.status},position:positions[n.id]??{x:100,y:100}})),
      ...network.edges.map((e,i)=>({data:{id:`edge-${i}`,source:e.source,target:e.target}}))
    ]
    const cy = cytoscape({container:ref.current,elements,layout:{name:'preset',fit:true,padding:compact?15:35},minZoom:.35,maxZoom:2,
      style:[
        {selector:'node',style:{'label':'data(label)','text-valign':'bottom','text-halign':'center','color':'#a9bacb','font-size':compact?9:11,'font-family':'DM Mono, monospace','text-margin-y':8,'background-color':'#142638','border-width':1,'border-color':'#416278','width':compact?34:42,'height':compact?34:42,'overlay-opacity':0}},
        {selector:'node[zone = "RESTRICTED"]',style:{'background-color':'#2a2730','border-color':'#c49c63'}},
        {selector:'node[zone = "DMZ"]',style:{'background-color':'#153b3a','border-color':'#55e6c1'}},
        {selector:'edge',style:{'width':1.4,'line-color':'#294356','target-arrow-color':'#416579','target-arrow-shape':'triangle','arrow-scale':.7,'curve-style':'bezier','opacity':.9}},
        {selector:'.filtered',style:{'opacity':.13}},
        {selector:'.matched',style:{'border-width':3,'border-color':'#55e6c1','color':'#e7fff8'}},
        {selector:':selected',style:{'border-width':3,'border-color':'#55e6c1','background-color':'#1d4b4b'}}
      ]})
    cyRef.current=cy
    if (onOpen) cy.on('tap','node',onOpen)
    cy.on('tap','node',(event: cytoscape.EventObject)=>{const d=event.target.data();onHostSelect?.({id:d.id,hostname:d.label,role:d.role,zone:d.zone})})
    cy.on('tap','edge',(event: cytoscape.EventObject)=>{const d=event.target.data();onEdgeSelect?.({source:d.source,target:d.target})})
    return ()=>{cy.destroy();cyRef.current=null}
  },[network,compact,onOpen,onHostSelect,onEdgeSelect])
  useEffect(()=>{
    const cy=cyRef.current
    if(!cy)return
    const q=filter.trim().toLowerCase()
    cy.nodes().forEach((node: cytoscape.NodeSingular)=>{
      const match=!q||`${node.data('label')} ${node.data('role')} ${node.data('zone')}`.toLowerCase().includes(q)
      node.toggleClass('matched',!!q&&match);node.toggleClass('filtered',!!q&&!match)
    })
    cy.edges().forEach((edge: cytoscape.EdgeSingular)=>{
      const visible=!q||edge.source().hasClass('matched')||edge.target().hasClass('matched')
      edge.style('opacity',visible?0.9:0.1)
    })
  },[filter,network])
  if(!network) return <div className="network-loading"><div className="loading-pulse"/><span>Connecting to topology service…</span></div>
  return <div className={`cytoscape-wrap ${compact?'compact':''}`}><div className="network-watermark">MIRAGENET / SIMULATED TRUST GRAPH</div><div ref={ref} className="cytoscape-canvas"/>{!compact&&<div className="network-footnote"><span><i/> Simulator reachability only</span><span>Topology model · v1</span></div>}</div>
}
