import {Typography} from '@shuku/course-style/react';

export function CoverPage({title}: {title: string}) {
  return <section style={{height: '100%', display: 'grid', placeContent: 'center', gap: 32, textAlign: 'center'}}>
    <Typography as="h1" variant="h1" tone="accent">{title}</Typography>
    <Typography variant="subtitle">边长变成 2 倍，面积也会变成 2 倍吗？</Typography>
  </section>;
}
