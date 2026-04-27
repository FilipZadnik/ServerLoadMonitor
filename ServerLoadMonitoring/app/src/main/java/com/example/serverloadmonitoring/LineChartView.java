package com.example.serverloadmonitoring;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Shader;
import android.util.AttributeSet;
import android.view.View;

import androidx.annotation.Nullable;

import java.util.ArrayList;
import java.util.List;

public class LineChartView extends View {
    private final List<Float> dataPoints = new ArrayList<>();
    private final Paint linePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path linePath = new Path();
    private final Path fillPath = new Path();

    private int lineColor = Color.BLUE;
    private float maxValue = 100f;

    public LineChartView(Context context) {
        super(context);
        init();
    }

    public LineChartView(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    private void init() {
        linePaint.setStyle(Paint.Style.STROKE);
        linePaint.setStrokeWidth(6.5f);
        linePaint.setStrokeCap(Paint.Cap.ROUND);
        linePaint.setStrokeJoin(Paint.Join.ROUND);

        fillPaint.setStyle(Paint.Style.FILL);
    }

    public void setData(List<Float> data, float maxValue) {
        this.dataPoints.clear();
        if (data != null) {
            this.dataPoints.addAll(data);
        }
        this.maxValue = Math.max(1f, maxValue);
        invalidate();
    }

    public void setLineColor(int color) {
        this.lineColor = color;
        linePaint.setColor(color);
        updateGradient();
        invalidate();
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        updateGradient();
    }

    private void updateGradient() {
        float height = getHeight();
        if (height <= 0) return;
        int startColor = Color.argb(100, Color.red(lineColor), Color.green(lineColor), Color.blue(lineColor));
        int endColor = Color.argb(0, Color.red(lineColor), Color.green(lineColor), Color.blue(lineColor));
        fillPaint.setShader(new LinearGradient(0, 0, 0, height, startColor, endColor, Shader.TileMode.CLAMP));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (dataPoints.size() < 2) {
            return;
        }

        float width = getWidth();
        float height = getHeight();

        linePath.reset();
        fillPath.reset();

        float xStep = width / (dataPoints.size() - 1);

        for (int i = 0; i < dataPoints.size(); i++) {
            float val = dataPoints.get(i);
            float x = i * xStep;
            float y = height - (val / maxValue * height);

            if (i == 0) {
                linePath.moveTo(x, y);
                fillPath.moveTo(x, height);
                fillPath.lineTo(x, y);
            } else {
                linePath.lineTo(x, y);
                fillPath.lineTo(x, y);
            }

            if (i == dataPoints.size() - 1) {
                fillPath.lineTo(x, height);
                fillPath.close();
            }
        }

        canvas.drawPath(fillPath, fillPaint);
        canvas.drawPath(linePath, linePaint);
    }
}
