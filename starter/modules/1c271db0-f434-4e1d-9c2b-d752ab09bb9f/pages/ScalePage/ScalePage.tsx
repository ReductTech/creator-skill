import {useState} from 'react';
import {ContentBlock, RangeControl, Typography} from '@shuku/course-style/react';

export function ScalePage({title}: {title: string}) {
  const [scale, setScale] = useState(1);
  return <ContentBlock title={title} subtitle="拖动滑杆，观察长度和面积的变化。">
    <div style={{display: 'grid', gridTemplateColumns: '2fr 1fr', alignItems: 'center', gap: 80, minHeight: 450}}>
      <div aria-hidden="true" style={{display: 'flex', justifyContent: 'center', alignItems: 'end', gap: 48}}>
        <div style={{width: 110, height: 110, border: '2px dashed #526678', boxSizing: 'border-box'}} />
        <div style={{width: scale * 110, height: scale * 110, background: '#176b87'}} />
      </div>
      <div style={{display: 'grid', gap: 24}}>
        <RangeControl label="放大倍数" min={1} max={3} step={0.25} value={scale}
          onChange={event => setScale(event.currentTarget.valueAsNumber)} />
        <Typography variant="body">边长 {scale.toFixed(2)} 倍</Typography>
        <Typography variant="body" tone="accent">面积 {(scale ** 2).toFixed(2)} 倍</Typography>
      </div>
    </div>
  </ContentBlock>;
}
