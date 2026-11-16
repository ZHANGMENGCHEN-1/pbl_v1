import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'

/** Procedural model: no external GLB, texture downloads, or asset license needed. */
export function createRobotModel(){
  const root=new THREE.Group()
  const shell=new THREE.MeshStandardMaterial({color:0xf3efff,roughness:.3,metalness:.08})
  const white=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.28,metalness:.08})
  const violet=new THREE.MeshStandardMaterial({color:0xb5a0df,roughness:.4,metalness:.16})
  const deepViolet=new THREE.MeshStandardMaterial({color:0x8762ca,roughness:.3,metalness:.18})
  const screen=new THREE.MeshStandardMaterial({color:0x252a45,roughness:.32,metalness:.12})
  const mint=new THREE.MeshStandardMaterial({color:0x8dedcf,emissive:0x43cfa6,emissiveIntensity:.5,roughness:.35})
  const pink=new THREE.MeshStandardMaterial({color:0xdba3cd,emissive:0xa668b9,emissiveIntensity:.15})
  const antennaMaterial=mint.clone()
  function add(parent:THREE.Object3D,geometry:THREE.BufferGeometry,material:THREE.Material,x=0,y=0,z=0){
    const mesh=new THREE.Mesh(geometry,material);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh
  }
  const rounded=(w:number,h:number,d:number,r:number)=>new RoundedBoxGeometry(w,h,d,4,r)
  function facePanel(){
    const w=1.02,h=.575,r=.25,shape=new THREE.Shape()
    shape.moveTo(-w+r,-h);shape.lineTo(w-r,-h);shape.quadraticCurveTo(w,-h,w,-h+r)
    shape.lineTo(w,h-r);shape.quadraticCurveTo(w,h,w-r,h)
    shape.lineTo(-w+r,h);shape.quadraticCurveTo(-w,h,-w,h-r)
    shape.lineTo(-w,-h+r);shape.quadraticCurveTo(-w,-h,-w+r,-h)
    return new THREE.ExtrudeGeometry(shape,{depth:.14,bevelEnabled:false,curveSegments:12,steps:1})
  }
  const head=new THREE.Group();head.position.y=3.05;root.add(head)
  add(head,rounded(2.42,1.76,1.3,.4),violet,0,0,-.07)
  add(head,rounded(2.36,1.7,1.32,.39),white)
  add(head,facePanel(),screen,0,0,.59)
  for(const side of [-1,1]){
    const ear=add(head,new THREE.CylinderGeometry(.29,.29,.24,24),violet,side*1.25,0,-.05);ear.rotation.z=Math.PI/2
    const cap=add(head,new THREE.CylinderGeometry(.19,.19,.025,24),shell,side*1.38,0,-.05);cap.rotation.z=Math.PI/2
    const cheek=add(head,new THREE.SphereGeometry(1,16,10),pink,side*.74,-.16,.746);cheek.scale.set(.09,.045,.015)
  }
  const eyes=[-.44,.44].map(x=>{
    const eye=add(head,new THREE.CapsuleGeometry(.1,.15,4,12),mint,x,.09,.753)
    return eye
  })
  const smileCurve=new THREE.QuadraticBezierCurve3(new THREE.Vector3(-.23,-.18,.758),new THREE.Vector3(0,-.4,.758),new THREE.Vector3(.23,-.18,.758))
  const smile=add(head,new THREE.TubeGeometry(smileCurve,20,.027,8,false),mint)
  add(head,new THREE.CylinderGeometry(.045,.045,.28,12),violet,0,1.01,0)
  const antenna=add(head,new THREE.SphereGeometry(.145,24,16),antennaMaterial,0,1.23,0)
  for(let i=0;i<3;i++)add(head,new THREE.SphereGeometry(.025,8,6),violet,-.54+i*.12,.63,.39)

  add(root,new THREE.CylinderGeometry(.23,.23,.22,20),violet,0,2.16,0)
  add(root,rounded(1.47,1.28,1.04,.33),shell,0,1.46,0)
  add(root,rounded(1.25,.14,.96,.065),violet,0,.94,0)
  const badge=add(root,new THREE.CylinderGeometry(.31,.31,.07,32),deepViolet,0,1.55,.55);badge.rotation.x=Math.PI/2
  const star=new THREE.Shape()
  for(let i=0;i<10;i++){
    const angle=Math.PI/2+i*Math.PI/5,r=i%2===0?.205:.095,x=Math.cos(angle)*r,y=Math.sin(angle)*r
    if(i===0)star.moveTo(x,y);else star.lineTo(x,y)
  }
  star.closePath()
  add(root,new THREE.ExtrudeGeometry(star,{depth:.025,bevelEnabled:true,bevelThickness:.008,bevelSize:.008,bevelSegments:2,steps:1}),white,0,1.55,.599)
  for(const side of [-1,1]){
    add(root,new THREE.CylinderGeometry(.15,.16,.35,16),violet,side*.4,.71,0)
    add(root,rounded(.56,.31,.85,.14),white,side*.42,.42,.15)
    add(root,rounded(.56,.055,.83,.025),violet,side*.42,.29,.15)
  }
  function arm(side:number){
    const pivot=new THREE.Group();pivot.position.set(side*.86,1.87,0);root.add(pivot)
    add(pivot,new THREE.SphereGeometry(.16,16,12),violet)
    add(pivot,new THREE.CapsuleGeometry(.13,.38,4,12),shell,0,-.31,0)
    add(pivot,new THREE.SphereGeometry(.15,16,12),violet,0,-.58,0)
    add(pivot,rounded(.32,.29,.28,.11),white,0,-.77,0)
    for(let i=0;i<3;i++)add(pivot,new THREE.CapsuleGeometry(.042,.1,3,8),white,(i-1)*.093,-.94,0)
    pivot.rotation.z=side===1?2.1:-.16
    return pivot
  }
  const leftArm=arm(-1),rightArm=arm(1)
  return {root,head,eyes,smile,leftArm,rightArm,antenna,antennaMaterial}
}
