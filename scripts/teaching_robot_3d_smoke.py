"""Actual WebGL rendering/rotation and graceful fallback; Vite frontend at 5174."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:5174/projects/teaching-agent')
    robot=page.locator('.robot-stage > .teaching-robot-view')
    expect(robot).to_have_attribute('data-renderer','three',timeout=30000)
    expect(robot.locator('canvas')).to_be_visible()
    assert page.locator('canvas').count()==1,'Chat avatars must not create WebGL contexts'
    canvas=robot.locator('canvas')
    before=canvas.screenshot()
    box=canvas.bounding_box()
    page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.5)
    page.mouse.down();page.mouse.move(box['x']+box['width']*.83,box['y']+box['height']*.55,steps=15);page.mouse.up()
    # Wait for OrbitControls damping to settle using requestAnimationFrame.
    page.evaluate('()=>new Promise(resolve=>{let n=0;function frame(){if(++n===45)resolve();else requestAnimationFrame(frame)}frame()})')
    after=canvas.screenshot()
    assert before!=after,'Dragging must change the 3D viewpoint'
    page.get_by_role('button',name='更多',exact=True).click()
    page.get_by_role('menuitem',name='小知转回正面',exact=True).click()
    Path('test-results').mkdir(exist_ok=True)
    page.screenshot(path='test-results/teaching-robot-3d.png',full_page=True)
    robot.evaluate("el=>{window.robotMoods=[];window.robotObserver=new MutationObserver(()=>window.robotMoods.push(el.dataset.mood));window.robotObserver.observe(el,{attributes:true,attributeFilter:['data-mood']})}")
    page.get_by_role('button',name='你好，小知',exact=True).click()
    page.get_by_role('button',name='我们试试',exact=True).click()
    page.get_by_role('textbox',name='和小知说说你的问题',exact=True).fill('我想问一个问题')
    page.get_by_role('button',name='发送',exact=True).click()
    expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible(timeout=10000)
    assert set(page.evaluate('window.robotMoods'))>={'thinking','talking','ready'}
    page.evaluate('window.robotObserver.disconnect()')
    assert page.locator('canvas').count()==1
    canvas.evaluate("canvas=>{const ext=canvas.getContext('webgl2').getExtension('WEBGL_lose_context');if(ext)ext.loseContext();else canvas.dispatchEvent(new Event('webglcontextlost',{cancelable:true}))}")
    expect(robot).to_have_attribute('data-renderer','svg')
    expect(robot.locator('canvas')).to_have_count(0)
    expect(robot.locator('svg')).to_be_visible()
    page.get_by_role('link',name='返回项目首页',exact=True).click()
    expect(page.locator('.home-teaching-art .teaching-robot-view')).to_have_attribute('data-renderer','three',timeout=30000)
    page.locator('.home-project-card.teaching').click()
    expect(robot).to_have_attribute('data-renderer','three',timeout=30000)
    assert not errors,errors
    page.close()

    fallback=browser.new_page(viewport={'width':390,'height':844})
    fallback.add_init_script("""const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){
      if(type==='webgl2'||type==='webgl'||type==='experimental-webgl')return null;
      return original.call(this,type,...args);
    };""")
    fallback.goto('http://127.0.0.1:5174/projects/teaching-agent')
    expect(fallback.locator('.robot-stage .robot-fallback svg')).to_be_visible()
    expect(fallback.locator('.robot-stage canvas')).to_have_count(0)
    fallback.get_by_role('button',name='你好，小知',exact=True).click()
    fallback.get_by_role('button',name='我们试试',exact=True).click()
    fallback.get_by_role('textbox',name='和小知说说你的问题',exact=True).fill('我想问一个问题')
    fallback.get_by_role('button',name='发送',exact=True).click()
    expect(fallback.get_by_role('button',name='发送',exact=True)).to_be_visible(timeout=10000)
    assert fallback.evaluate('document.documentElement.scrollWidth<=innerWidth')
    browser.close()
    print('Passed real Three.js canvas, rotation, reset, chat states, one-context avatar policy, context-loss recovery, route cleanup and no-WebGL mobile chat fallback.')
