const { createApp, ref, shallowRef } = Vue

const app = createApp({
    data () {
        return {
            chart_engine: null,
            chart_memory: null
        }
    },
    methods: {
        async buildCharts () {
            const ctx_util = document.getElementById('utilization-chart');
            this.chart_engine = shallowRef(new Chart(ctx_util, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: []
                },
                options: {
                    animation: {
                        duration: 0
                    },
                    elements: {
                        point:{
                            radius: 0
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'GPU Engine Utilization (%)'
                        }
                    },
                    scales: {
                        x: {
                            display: false,
                            scaleLabel: {
                                display: true
                            }
                        },
                        y: {
                            display: true,
                            min: 0,
                            max: 100,
                            ticks: {
                                beginAtZero: true,
                                steps: 10,
                                stepValue: 5,
                                
                            }
                        }
                    },
                }
            }));
            const ctx_mem = document.getElementById('memory-chart');
            this.chart_memory = shallowRef(new Chart(ctx_mem, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: []
                },
                options: {
                    animation: {
                        duration: 0
                    },
                    elements: {
                        point:{
                            radius: 0
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'GPU Memory Utilization (%)'
                        }
                    },
                    scales: {
                        x: {
                            display: false,
                            scaleLabel: {
                                display: true
                            }
                        },
                        y: {
                            display: true,
                            min: 0,
                            max: 100,
                            ticks: {
                                beginAtZero: true,
                                steps: 10,
                                stepValue: 5,
                                
                            }
                        }
                    },
                }
            }));
        },
        request (options, path, json=true) {
            return new Promise(function (resolve, reject) {
                var xhr = new XMLHttpRequest(); 
                xhr.open("POST", path, true); 
                if (json) {
                    xhr.setRequestHeader("Content-type", "application/json;charset=UTF-8"); 
                }
                xhr.onreadystatechange = function () {  
                    if (xhr.readyState == 4 && xhr.status == 200) {
                        var json = JSON.parse(xhr.responseText);
                        if (Object.keys(json).includes('errors') && json['errors'].length != 0) { // if errors occur
                            console.log('server:', json['errors'])
                        } resolve(json);
                    }
                }
                xhr.onerror = function(e) {
                    reject({'errors': ['error during request: no connection']})
                }
                xhr.send(JSON.stringify(options)); 
            });
        },
        sleep (seconds) {
            return new Promise(function(resolve) {
                setTimeout(function() {
                    resolve(0);
                }, 1000*seconds);
            });
        },
        async main () {

            while (true) {
                
                // create pkg
                let pkg = {}

                // make API query
                const response = await this.request(pkg, '/');
                
                // show errors if any
                if (response.errors.length > 0) {
                    console.log('errors:', response.errors)}

                

                // iterate through data

                // reset timeseries
                this.chart_engine.data.datasets = [];
                this.chart_memory.data.datasets = [];
                this.chart_memory.data.labels = [];
                this.chart_engine.data.labels = [];

                // labels = [];
                for (const id in response.data) {
                    
                    const gpu = response.data[id];

                    console.log('gpu', gpu.engine_usage_timeseries)

                    // build chart for this GPU
                    this.chart_engine.data.datasets.push({
                        label: `[ ${gpu.id} ] ${gpu.name}`,
                        data: gpu.engine_usage_timeseries,
                        borderWidth: 2,
                    })

                    this.chart_memory.data.datasets.push({
                        label: `[ ${gpu.id} ] ${gpu.name}`,
                        data: gpu.memory_usage_timeseries,
                        borderWidth: 2,
                    })
                    

                }

                // fill the labels for x-axis
                for (let i = 0; i < this.chart_engine.data.datasets[0].data.length; i++) {
                    this.chart_engine.data.labels.push(0)
                    this.chart_memory.data.labels.push(0)
                }

                // this.chart_engine.data.labels = labels;
                this.chart_engine.update();
                this.chart_memory.update();

                await this.sleep(.1)
            }
    
        }

    },
    async mounted () {

        try {

            // build chart
            await this.buildCharts();
            await this.sleep(1);

            // run main function
            this.main()

        } catch (error) {

            console.log('mount hook error:', error)
        
        }

    },

})

app.mount('#vue-app')