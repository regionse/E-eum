// node_modules 가 없으면(=처음 켠 노트북) 자동으로 npm install 해준다.
// package.json 의 "predev" 에 연결돼 있어서, npm run dev 를 치면 이 파일이 먼저 돈다.
// 이미 설치돼 있으면 아무것도 안 하고 즉시 넘어간다(빠름).
import { existsSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const installed = existsSync(join(root, 'node_modules', 'vite'))

if (!installed) {
  console.log('\n📦 처음 실행이라 필요한 라이브러리를 설치할게요. (1~2분, 최초 1회만)\n')
  execSync('npm install', { cwd: root, stdio: 'inherit' })
  console.log('\n✅ 설치 완료! 이제 서버를 켤게요.\n')
}
