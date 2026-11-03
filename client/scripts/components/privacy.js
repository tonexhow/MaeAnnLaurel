import {openModal,paragraph} from './modal.js';
export function initPrivacy(){
  document.querySelectorAll('[data-open-privacy]').forEach(button=>button.addEventListener('click',()=>{
    const content=document.createElement('div');
    const items=[
      ['What you provide','The contact form asks for your name, email address, subject, message and consent. You can choose not to submit it. Please do not include passwords or other sensitive information.'],
      ['How your message is delivered','A dedicated sending account forwards your enquiry to the portfolio owner. Your validated email is used as the reply-to address so the owner can respond. Email delivery providers may retain messages under their own policies.'],
      ['Technical records','This portfolio has no application database. The contact service may temporarily hold request references and counts in server memory to discourage repeated submissions. This protection is not shared across server instances and disappears when an instance stops. Hosting providers may keep operational logs.'],
      ['Other services','Your browser may retain your theme preference and a recent submission reference. The live contact form uses Cloudflare Turnstile, which processes security signals. Hosting and email providers may also process access and delivery information.'],
      ['Delivery and requests','Email-server acceptance does not guarantee that the message reaches an inbox. A reference is shown after attempted submission. To ask about an enquiry or request deletion, use the reply email conversation or the contact method listed on this site.'],
    ];
    items.forEach(([heading,description])=>{const h=document.createElement('h3');h.textContent=heading;content.append(h,paragraph(description));});
    openModal({title:'Privacy & contact',eyebrow:'HOW ENQUIRIES ARE HANDLED',content,restoreFocus:button});
  }));
}
