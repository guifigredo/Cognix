/* Verificação visual opcional: node tests/qa_v98_playwright.cjs
   Requer Chromium e Playwright no ambiente de testes, não no computador escolar. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.COGNIX_TEST_URL || 'http://127.0.0.1:8208';
const out = process.env.COGNIX_TEST_SCREENSHOTS || '/tmp';
const creds = fs.readFileSync(path.join(__dirname, '../data/ACESSOS-DEMO-LOCAL.txt'), 'utf8');

function password(email) {
  const line = creds.split(/\r?\n/).find(x => x.startsWith(email + ' | '));
  if (!line) throw new Error('Conta de teste não encontrada: ' + email);
  return line.split(' | ')[1].trim();
}

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'/usr/bin/chromium',
    args:['--no-sandbox', '--disable-dev-shm-usage']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const login = async email => {
      await page.goto(base);
      await page.locator('#auth-form [name=email]').fill(email);
      await page.locator('#auth-form [name=password]').fill(password(email));
      await page.locator('#auth-form button[type=submit]').click();
      await page.locator('.sidebar').waitFor({timeout:15000});
    };
    const nav=async name=>{
      await page.locator('.sidebar nav button').filter({hasText:name}).first().click();
      await page.waitForTimeout(350);
    };
    await login('alice.fontes@cognix.test');
    await nav('Vocação');
    await page.locator('#student-vocation-form').waitFor();
    await page.screenshot({path:path.join(out,'cognix_v98_vocation.png'),fullPage:true});
    await nav('Notas da escola');
    await page.locator('.grade-projection summary').first().click();
    await page.screenshot({path:path.join(out,'cognix_v98_grades.png'),fullPage:true});
    await nav('Minha Trilha ENEM');
    await page.locator('#student-trail-settings').waitFor();
    await page.screenshot({path:path.join(out,'cognix_v98_student_trail.png'),fullPage:true});
    await page.locator('.sidebar .signout').click();
    await login('rafael.monteiro@cognix.test');
    await nav('Trilha ENEM');
    await page.locator('.trail-priority-section').waitFor({timeout:15000});
    await page.screenshot({path:path.join(out,'cognix_v98_teacher_priorities.png'),fullPage:true});
    if(errors.length)throw new Error('Erros JS: '+errors.join(' | '));
    console.log('QA aprovado: vocação, projeção de notas, trilha individual e prioridades da turma.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
