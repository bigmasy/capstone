import { uk } from "../../i18n/uk";
import Accordion from "../Accordion/Accordion";
import Section from "./Section";

const text = uk.landing.faq;

const items = text.items.map((item) => ({
  heading: item.question,
  content: <p>{item.answer}</p>,
}));

/** Frequently asked questions as a group of disclosure buttons. */
const FaqSection = () => (
  <Section heading={text.heading}>
    <Accordion items={items} />
  </Section>
);

export default FaqSection;
