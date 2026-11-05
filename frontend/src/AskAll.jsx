import Ask from './Ask.jsx'
import { SUGGEST_ALL } from './labels'

export default function AskAll({ onOpen }) {
  return (
    <>
      <h1>Ask all documents</h1>
      <p className="lede">Compare and search across everything you have uploaded. Sources link back to the documents so you can check the answer yourself.</p>
      <div className="wide-ask"><Ask suggestions={SUGGEST_ALL} onOpenDoc={onOpen} /></div>
    </>
  )
}
