<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { createRobotModel } from './robotModel'

const props=withDefaults(defineProps<{mood:'ready'|'thinking'|'talking';interactive?:boolean}>(),{interactive:true})
const emit=defineEmits<{ready:[];unsupported:[]}>()
const host=ref<HTMLDivElement>()
let dispose=()=>{},reset=()=>{}
defineExpose({reset:()=>reset()})

onMounted(()=>{
  const container=host.value
  if(!container)return
  let renderer:THREE.WebGLRenderer|undefined,controls:OrbitControls|undefined,observer:ResizeObserver|undefined,visibilityObserver:IntersectionObserver|undefined
  const canvas=document.createElement('canvas')
  const scene=new THREE.Scene()
  let destroyed=false,visible=true,reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches
  let lost=false
  const pointer=new THREE.Vector2(),target=new THREE.Vector2()
  const materials=new Set<THREE.Material>(),geometries=new Set<THREE.BufferGeometry>()
  const fail=()=>{if(!lost&&!destroyed){lost=true;emit('unsupported')}}
  const contextLost=(event:Event)=>{event.preventDefault();fail()}
  const trackPointer=(event:PointerEvent)=>{
    if(!props.interactive||event.buttons)return
    const rect=canvas.getBoundingClientRect()
    target.set(THREE.MathUtils.clamp((event.clientX-rect.left)/rect.width*2-1,-1,1),THREE.MathUtils.clamp((event.clientY-rect.top)/rect.height*2-1,-1,1))
  }
  const leavePointer=()=>target.set(0,0)
  let onVisibility=()=>{}
  dispose=()=>{
    if(destroyed)return
    destroyed=true;renderer?.setAnimationLoop(null);observer?.disconnect();visibilityObserver?.disconnect();controls?.dispose()
    canvas.removeEventListener('webglcontextlost',contextLost);canvas.removeEventListener('pointermove',trackPointer);canvas.removeEventListener('pointerleave',leavePointer)
    document.removeEventListener('visibilitychange',onVisibility)
    scene.traverse(object=>{if(object instanceof THREE.Mesh){geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material])materials.add(material)}if(object instanceof THREE.DirectionalLight)object.shadow.dispose()})
    for(const geometry of geometries)geometry.dispose()
    for(const material of materials)material.dispose()
    renderer?.dispose();renderer?.forceContextLoss();canvas.remove()
  }
  try{
    const context=canvas.getContext('webgl2',{alpha:true,antialias:true,powerPreference:'low-power'})
    if(!context){fail();return}
    renderer=new THREE.WebGLRenderer({canvas,context,alpha:true,antialias:true,powerPreference:'low-power'})
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,2))
    renderer.setClearColor(0x000000,0)
    renderer.outputColorSpace=THREE.SRGBColorSpace
    renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2
    renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap
    canvas.setAttribute('aria-hidden','true')
    canvas.style.display='block';canvas.style.width='100%';canvas.style.height='100%'
    container.appendChild(canvas)
    canvas.addEventListener('webglcontextlost',contextLost)
    canvas.addEventListener('pointermove',trackPointer);canvas.addEventListener('pointerleave',leavePointer)

    const camera=new THREE.PerspectiveCamera(34,1,.1,40)
    const initialPosition=new THREE.Vector3(2.45,3.0,8.1)
    camera.position.copy(initialPosition)
    controls=new OrbitControls(camera,canvas)
    controls.target.set(0,2.2,0);controls.enableDamping=true;controls.dampingFactor=.09;controls.enableZoom=false;controls.enablePan=false
    controls.minPolarAngle=Math.PI*.28;controls.maxPolarAngle=Math.PI*.62;controls.rotateSpeed=.7
    reset=()=>{controls?.reset();target.set(0,0)}
    scene.add(new THREE.HemisphereLight(0xf4f4ff,0x9a83b8,2.4))
    const key=new THREE.DirectionalLight(0xfffaf4,4);key.position.set(-3,7,6);key.castShadow=true
    key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-3;key.shadow.camera.right=3;key.shadow.camera.top=6;key.shadow.camera.bottom=-1;key.shadow.camera.near=.5;key.shadow.camera.far=18;key.shadow.normalBias=.03;key.shadow.bias=-.0002;scene.add(key)
    const fill=new THREE.DirectionalLight(0xc4b8ff,2);fill.position.set(5,3,-4);scene.add(fill)
    const front=new THREE.DirectionalLight(0xffffff,.6);front.position.set(0,2,8);scene.add(front)
    const model=createRobotModel();scene.add(model.root)
    const floor=new THREE.Mesh(new THREE.CircleGeometry(2.1,48),new THREE.ShadowMaterial({color:0x6f5196,opacity:.13}))
    floor.rotation.x=-Math.PI/2;floor.position.y=.03;floor.receiveShadow=true;scene.add(floor)
    const ring=new THREE.Mesh(new THREE.TorusGeometry(1.08,.012,6,80),new THREE.MeshBasicMaterial({color:0xd9cbee,transparent:true,opacity:.7}))
    ring.rotation.x=-Math.PI/2;ring.position.y=.04;scene.add(ring)
    const start=performance.now()
    let lastFrame=0
    const animate=(now:number)=>{
      if(destroyed||lost||!visible||document.hidden||!renderer)return
      if(now-lastFrame<32)return // Cap at ~30fps for this decorative scene.
      lastFrame=now
      const time=(now-start)/1000
      if(!reduced){
        pointer.lerp(target,.07)
        model.root.position.y=Math.sin(time*1.7)*.065
        model.root.rotation.z=Math.sin(time*.8)*.013
        model.head.rotation.y=pointer.x*.18+Math.sin(time*.65)*.025
        model.head.rotation.x=pointer.y*.1
        const blink=time%5.4,eyeScale=blink<.15?Math.max(.08,Math.abs(blink-.075)/.075):1
        for(const eye of model.eyes)eye.scale.y=eyeScale
        model.rightArm.rotation.z=2.1+Math.sin(time*(props.mood==='talking'?7:1.4))*(props.mood==='talking'?.28:.045)
        model.leftArm.rotation.z=-.16+Math.sin(time*1.6)*.035
        model.smile.scale.y=props.mood==='talking'?1+Math.sin(time*11)*.16:1
        model.antennaMaterial.emissiveIntensity=props.mood==='thinking'?.7+Math.sin(time*5)*.6:.35
      }
      model.antennaMaterial.color.setHex(props.mood==='talking'?0xbda2ee:0x8dedcf)
      if(reduced)model.antennaMaterial.emissiveIntensity=props.mood==='thinking'?.85:.35
      controls?.update();renderer.render(scene,camera)
    }
    const resize=()=>{
      if(!renderer)return
      const width=container.clientWidth,height=container.clientHeight
      if(!width||!height)return
      camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height,false)
      renderer.shadowMap.enabled=width>=150
      if(controls)controls.enabled=props.interactive&&width>=150
      canvas.style.touchAction=props.interactive&&width>=150?'none':'pan-y'
      renderer.render(scene,camera)
    }
    observer=new ResizeObserver(resize);observer.observe(container);resize();controls.update();controls.saveState();renderer.render(scene,camera)
    onVisibility=()=>{if(renderer)renderer.setAnimationLoop(document.hidden||!visible?null:animate)}
    document.addEventListener('visibilitychange',onVisibility)
    visibilityObserver=new IntersectionObserver(entries=>{visible=!!entries[0]?.isIntersecting;onVisibility()})
    visibilityObserver.observe(container)
    renderer.setAnimationLoop(animate)
    emit('ready')
  }catch{
    fail();dispose()
  }
})
onBeforeUnmount(()=>dispose())
</script>
<template><div ref="host" class="robot-scene"/></template>
<style scoped>.robot-scene{position:absolute;inset:0;width:100%;height:100%;overflow:hidden}</style>
